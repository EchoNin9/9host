"""
SiteStoragePort — atomic versioned storage for compiled sites (docs/SPEC.md §3 Module 4).

Layout in s3://9host-sites:
  {tenant}/{site_id}/published/v{N}/...        immutable version (+ manifest.json)
  {tenant}/{site_id}/published/current/...     live copy served at /
  {tenant}/{site_id}/published/current.json    pointer {"version", "published_at", "manifest"}
  {tenant}/{site_id}/draft/...                 draft preview (no versioning)
  {tenant}/default/... + {tenant}/default.json first published site of a tenant (legacy)

HostMappingKVS (CloudFront KeyValueStore 9host-site-hosts-kvs, read by cf-site-content.js):
  "<lowercase hostname>" -> '{"tenant":"<tenant_slug>","site_id":"<site_id>"}'
  "__preview_jwt_secret__" -> sha256-derived draft-preview HS256 key (written by OpenTofu)

S3SiteStorageAdapter and InMemorySiteStorage share all logic and differ only in five
storage primitives, so tests of the in-memory adapter exercise the real flow.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Protocol

import boto3
from botocore.exceptions import ClientError

from site_compiler import CompiledSiteBundle

S3_SITES_BUCKET = "9host-sites"
HTML_CACHE_CONTROL = "max-age=60, s-maxage=300"
ASSET_CACHE_CONTROL = "max-age=31536000, immutable"
DRAFT_CACHE_CONTROL = "no-cache, no-store, must-revalidate"

KVS_ARN_ENV = "SITE_HOSTS_KVS_ARN"
_KVS_CONFLICT_CODES = ("ConflictException", "PreconditionFailed")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HostMappingKVS — CloudFront KeyValueStore writes (ETag optimistic concurrency).
# All public functions are best-effort: they log and swallow failures so a KVS
# outage never fails a publish/domain operation that already succeeded, and they
# are a logged no-op when SITE_HOSTS_KVS_ARN is unset (local dev / tests).
# ---------------------------------------------------------------------------

_kvs_client = None


def _get_kvs_client():
    """Module-cached client. Tests replace this via monkeypatch.
    NOTE: the KVS data-plane API is SigV4A-signed -> needs awscrt (botocore[crt]) at runtime."""
    global _kvs_client
    if _kvs_client is None:
        _kvs_client = boto3.client("cloudfront-keyvaluestore", region_name="us-east-1")
    return _kvs_client


def normalize_hostname(hostname: str) -> str:
    """Lowercase, strip whitespace / port / trailing dot — matches cf-site-content.js lookup keys."""
    return (hostname or "").strip().lower().split(":")[0].rstrip(".")


def _kvs_write(key: str, value: str | None) -> bool:
    """PutKey (value given) or DeleteKey (value None) with the store's current ETag.
    Retries once on an ETag conflict. Returns False when KVS is not configured."""
    arn = (os.environ.get(KVS_ARN_ENV) or "").strip()
    if not arn:
        logger.info("%s unset; skipping KVS %s of %r", KVS_ARN_ENV, "put" if value is not None else "delete", key)
        return False
    client = _get_kvs_client()
    for attempt in range(2):
        etag = client.describe_key_value_store(KvsARN=arn)["ETag"]
        try:
            if value is not None:
                client.put_key(KvsARN=arn, Key=key, Value=value, IfMatch=etag)
            else:
                client.delete_key(KvsARN=arn, Key=key, IfMatch=etag)
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if value is None and code == "ResourceNotFoundException":
                return True  # key already absent — delete is idempotent
            if code in _KVS_CONFLICT_CODES and attempt == 0:
                continue  # another writer bumped the ETag; re-describe and retry once
            raise
    return False  # pragma: no cover


def put_host_mapping(hostname: str, tenant_slug: str, site_id: str) -> bool:
    """HostMappingKVS: lowercase hostname -> {"tenant", "site_id"} (SPEC §1B). Never raises.

    Returns True when the key was written (or KVS is not configured, so there is nothing to
    sync), False on incomplete input or a failed write so callers can retry later."""
    key = normalize_hostname(hostname)
    if not key or not tenant_slug or not site_id:
        logger.warning("put_host_mapping: missing hostname/tenant/site_id (%r, %r, %r)", hostname, tenant_slug, site_id)
        return False
    value = json.dumps({"tenant": tenant_slug, "site_id": site_id}, separators=(",", ":"))
    try:
        _kvs_write(key, value)
    except Exception:
        logger.exception("KVS put_host_mapping failed for %s -> %s/%s", key, tenant_slug, site_id)
        return False
    return True


def delete_host_mapping(hostname: str) -> None:
    """Remove a hostname from HostMappingKVS. Idempotent and best-effort."""
    key = normalize_hostname(hostname)
    if not key:
        return
    try:
        _kvs_write(key, None)
    except Exception:
        logger.exception("KVS delete_host_mapping failed for %s", key)


def list_host_mappings() -> list[dict]:
    """All HostMappingKVS routing entries as {"hostname", "tenant", "site_id"} (paginated ListKeys).
    Internal keys starting with "__" (e.g. the preview JWT secret) are never returned.
    Returns [] when SITE_HOSTS_KVS_ARN is unset."""
    arn = (os.environ.get(KVS_ARN_ENV) or "").strip()
    if not arn:
        return []
    client = _get_kvs_client()
    entries: list[dict] = []
    kwargs = {"KvsARN": arn}
    while True:
        resp = client.list_keys(**kwargs)
        for item in resp.get("Items", []):
            key = item.get("Key") or ""
            if not key or key.startswith("__"):
                continue
            try:
                value = json.loads(item.get("Value") or "")
            except ValueError:
                value = None
            value = value if isinstance(value, dict) else {}
            entries.append({"hostname": key, "tenant": value.get("tenant", ""), "site_id": value.get("site_id", "")})
        if not resp.get("NextToken"):
            return entries
        kwargs["NextToken"] = resp["NextToken"]


def _cache_control(path: str) -> str:
    return HTML_CACHE_CONTROL if path.endswith((".html", ".xml", ".txt")) else ASSET_CACHE_CONTROL


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SiteStoragePort(Protocol):
    def publish(self, tenant_slug: str, site_id: str, bundle: CompiledSiteBundle, published_at: str) -> dict: ...
    def publish_draft(self, tenant_slug: str, site_id: str, bundle: CompiledSiteBundle) -> dict: ...
    def rollback(self, tenant_slug: str, site_id: str, version: int, now: str | None = None) -> dict | None: ...
    def sync_host_mapping(self, tenant_slug: str, site_id: str, hostnames: list[str]) -> None: ...
    def remove_host_mapping(self, hostnames: list[str]) -> None: ...


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
        """HostMappingKVS: map every hostname to {tenant, site_id}. Best-effort (never raises)."""
        for hostname in hostnames:
            put_host_mapping(hostname, tenant_slug, site_id)

    def remove_host_mapping(self, hostnames: list[str]) -> None:
        """Drop hostnames from HostMappingKVS (site deleted / slug changed / domain removed)."""
        for hostname in hostnames:
            delete_host_mapping(hostname)


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
        self.removed_host_mappings: list[str] = []

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

    def remove_host_mapping(self, hostnames):
        self.removed_host_mappings.extend(hostnames)

    def read(self, key: str) -> str | None:
        body = self._get(key)
        return body.decode("utf-8") if body is not None else None
