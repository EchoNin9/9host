"""
SiteStoragePort — atomic versioned storage for compiled sites (docs/SPEC.md §3 Module 4).

Layout in s3://9host-sites:
  {tenant}/{site_id}/published/v{N}/...        immutable version (+ manifest.json)
  {tenant}/{site_id}/published/current/...     live copy served at /
  {tenant}/{site_id}/published/current.json    pointer {"version", "published_at", "manifest"}
  {tenant}/{site_id}/draft/...                 draft preview (no versioning)
  {tenant}/default/... + {tenant}/default.json first published site of a tenant (legacy)

S3SiteStorageAdapter and InMemorySiteStorage share all logic and differ only in five
storage primitives, so tests of the in-memory adapter exercise the real flow.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Protocol

from botocore.exceptions import ClientError

from site_compiler import CompiledSiteBundle

S3_SITES_BUCKET = "9host-sites"
HTML_CACHE_CONTROL = "max-age=60, s-maxage=300"
ASSET_CACHE_CONTROL = "max-age=31536000, immutable"
DRAFT_CACHE_CONTROL = "no-cache, no-store, must-revalidate"


def _cache_control(path: str) -> str:
    return HTML_CACHE_CONTROL if path.endswith((".html", ".xml", ".txt")) else ASSET_CACHE_CONTROL


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SiteStoragePort(Protocol):
    def publish(self, tenant_slug: str, site_id: str, bundle: CompiledSiteBundle, published_at: str) -> dict: ...
    def publish_draft(self, tenant_slug: str, site_id: str, bundle: CompiledSiteBundle) -> dict: ...
    def rollback(self, tenant_slug: str, site_id: str, version: int, now: str | None = None) -> dict | None: ...
    def sync_host_mapping(self, tenant_slug: str, site_id: str, hostnames: list[str]) -> None: ...


class _SiteStorageBase:
    # --- primitives (per backend) ---
    def _put(self, key: str, body: bytes, content_type: str, cache_control: str | None = None) -> None:
        raise NotImplementedError

    def _copy(self, src_key: str, dst_key: str, cache_control: str) -> None:
        raise NotImplementedError

    def _get(self, key: str) -> bytes | None:
        raise NotImplementedError

    def _exists(self, key: str) -> bool:
        raise NotImplementedError

    def _list_versions(self, published_prefix: str) -> list[int]:
        raise NotImplementedError

    # --- shared flow ---
    def _get_json(self, key: str) -> dict | None:
        raw = self._get(key)
        return json.loads(raw.decode()) if raw is not None else None

    def _put_json(self, key: str, data: dict) -> None:
        self._put(key, json.dumps(data).encode("utf-8"), "application/json")

    def next_version(self, tenant_slug: str, site_id: str) -> int:
        """max(existing v* folders, current.json) + 1 — never reuses a version after a rollback."""
        prefix = f"{tenant_slug}/{site_id}/published/"
        versions = list(self._list_versions(prefix))
        current = self._get_json(f"{prefix}current.json") or {}
        versions.append(int(current.get("version", 0) or 0))
        return max(versions) + 1

    def publish(self, tenant_slug: str, site_id: str, bundle: CompiledSiteBundle, published_at: str) -> dict:
        prefix = f"{tenant_slug}/{site_id}/published/"
        version = self.next_version(tenant_slug, site_id)
        v_prefix = f"{prefix}v{version}/"
        is_default = not self._exists(f"{tenant_slug}/default.json")

        for path, body in bundle.files.items():
            cache = _cache_control(path)
            self._put(f"{v_prefix}{path}", body, bundle.content_types[path], cache)
            self._copy(f"{v_prefix}{path}", f"{prefix}current/{path}", cache)
            if is_default:
                self._copy(f"{v_prefix}{path}", f"{tenant_slug}/default/{path}", cache)

        self._put_json(f"{v_prefix}manifest.json", {
            "version": version,
            "published_at": published_at,
            "files": bundle.manifest.get("files", []),
        })
        self._put_json(f"{prefix}current.json", {
            "version": version,
            "published_at": published_at,
            "manifest": f"v{version}/manifest.json",
        })
        if is_default:
            self._put_json(f"{tenant_slug}/default.json", {"site_id": site_id, "published_at": published_at})

        return {
            "version": version,
            "published_at": published_at,
            "files_count": len(bundle.files),
            "is_default": is_default,
        }

    def publish_draft(self, tenant_slug: str, site_id: str, bundle: CompiledSiteBundle) -> dict:
        draft_prefix = f"{tenant_slug}/{site_id}/draft/"
        for path, body in bundle.files.items():
            self._put(f"{draft_prefix}{path}", body, bundle.content_types[path], DRAFT_CACHE_CONTROL)
        return {"files_count": len(bundle.files)}

    def rollback(self, tenant_slug: str, site_id: str, version: int, now: str | None = None) -> dict | None:
        """Copy v{N}/ to current/ and repoint current.json. Returns None if v{N} doesn't exist."""
        prefix = f"{tenant_slug}/{site_id}/published/"
        v_prefix = f"{prefix}v{version}/"
        manifest = self._get_json(f"{v_prefix}manifest.json")
        if not manifest or not manifest.get("files"):
            return None
        for entry in manifest["files"]:
            path = entry.get("path", "")
            if path:
                self._copy(f"{v_prefix}{path}", f"{prefix}current/{path}", _cache_control(path))
        now = now or _now()
        self._put_json(f"{prefix}current.json", {
            "version": version,
            "published_at": manifest.get("published_at", now),
            "manifest": f"v{version}/manifest.json",
        })
        return {"version": version, "rolled_back_at": now}

    def sync_host_mapping(self, tenant_slug: str, site_id: str, hostnames: list[str]) -> None:
        """Seam for HostMappingKVS (host -> {"tenant", "site_id"}). No-op until T-06
        implements the CloudFront KeyValueStore (9host-site-hosts-kvs) sync here."""
        return None


class S3SiteStorageAdapter(_SiteStorageBase):
    def __init__(self, s3_client, bucket: str = S3_SITES_BUCKET):
        self.s3 = s3_client
        self.bucket = bucket

    def _put(self, key, body, content_type, cache_control=None):
        kwargs = {"Bucket": self.bucket, "Key": key, "Body": body, "ContentType": content_type}
        if cache_control:
            kwargs["CacheControl"] = cache_control
        self.s3.put_object(**kwargs)

    def _copy(self, src_key, dst_key, cache_control):
        self.s3.copy_object(
            Bucket=self.bucket,
            CopySource={"Bucket": self.bucket, "Key": src_key},
            Key=dst_key,
            CacheControl=cache_control,
        )

    def _get(self, key):
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise

    def _exists(self, key):
        # Legacy semantics: any HeadObject failure (404, or 403 without ListBucket) => absent.
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def _list_versions(self, published_prefix):
        versions = []
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=published_prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                name = cp["Prefix"].rstrip("/").split("/")[-1]
                if name.startswith("v") and name[1:].isdigit():
                    versions.append(int(name[1:]))
        return versions


class InMemorySiteStorage(_SiteStorageBase):
    """Dict-backed storage for tests: objects[key] = (body, content_type, cache_control)."""

    def __init__(self):
        self.objects: dict[str, tuple[bytes, str, str | None]] = {}
        self.host_mappings: list[tuple[str, str, list[str]]] = []

    def _put(self, key, body, content_type, cache_control=None):
        self.objects[key] = (body, content_type, cache_control)

    def _copy(self, src_key, dst_key, cache_control):
        body, ctype, _ = self.objects[src_key]
        self.objects[dst_key] = (body, ctype, cache_control)

    def _get(self, key):
        obj = self.objects.get(key)
        return obj[0] if obj else None

    def _exists(self, key):
        return key in self.objects

    def _list_versions(self, published_prefix):
        versions = set()
        for key in self.objects:
            if key.startswith(published_prefix):
                name = key[len(published_prefix):].split("/", 1)[0]
                if "/" in key[len(published_prefix):] and name.startswith("v") and name[1:].isdigit():
                    versions.add(int(name[1:]))
        return sorted(versions)

    def sync_host_mapping(self, tenant_slug, site_id, hostnames):
        self.host_mappings.append((tenant_slug, site_id, list(hostnames)))

    def read(self, key: str) -> str | None:
        body = self._get(key)
        return body.decode("utf-8") if body is not None else None
