"""
TenantStore — deep repository over the 9host-main single table (docs/SPEC.md §3 Module 3).

Hides all pk/sk formatting and GSI queries. Every base-table query uses a partition key
TENANT#{slug} (tenant isolation); the only global lookup is resolve_site_slug via the
bySiteSlug GSI.

Bug #3 (SITE# sort-key collision): site metadata is written to SK=SITE_META#{id} and
mirrored to legacy SK=SITE#{id} (expand-contract). list_sites reads SITE_META# only. Tenants
whose sites exist only as legacy SITE#{id} rows are backfilled once (lazily) on the first
list_sites call, after which a MIGRATION#SITE_META marker row skips the legacy read.

Bug #4: adjust_storage_bytes uses ADD / conditional SET instead of the invalid greatest().
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Protocol

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from dynamodb_helpers import (
    SITE_META_PREFIX,
    gsi4pk_slug,
    gsi4sk_site,
    pk_tenant,
    query_by_site_slug,
    sk_site,
    sk_site_meta,
    sk_tenant,
    sk_user_profile,
)

CONTENT_TYPES = ("PAGE", "POST", "EVENT", "MEDIA")
SITE_META_MIGRATION_SK = "MIGRATION#SITE_META"
_KEY_ATTRS = frozenset(
    {"pk", "sk", "gsi1pk", "gsi1sk", "gsi2pk", "gsi2sk", "gsi3pk", "gsi3sk", "gsi4pk", "gsi4sk"}
)


class TenantStore(Protocol):
    # Tenant metadata & storage quota
    def get_tenant(self, tenant_slug: str) -> dict | None: ...
    def update_tenant(self, tenant_slug: str, updates: dict) -> dict: ...
    def adjust_storage_bytes(self, tenant_slug: str, delta_bytes: int) -> int: ...

    # Sites (fixes Bug #3: never scans PAGE/POST/EVENT/MEDIA items)
    def list_sites(self, tenant_slug: str) -> list[dict]: ...
    def get_site(self, tenant_slug: str, site_id: str) -> dict | None: ...
    def put_site(self, tenant_slug: str, site: dict) -> dict: ...
    def delete_site_cascade(self, tenant_slug: str, site_id: str) -> None: ...
    def resolve_site_slug(self, site_slug: str) -> dict | None: ...

    # Content (PAGE, POST, EVENT, MEDIA)
    def list_content(self, tenant_slug: str, site_id: str, content_type: str, status: str | None = None) -> list[dict]: ...
    def get_content(self, tenant_slug: str, site_id: str, content_type: str, item_id: str) -> dict | None: ...
    def put_content(self, tenant_slug: str, site_id: str, content_type: str, item: dict) -> dict: ...
    def delete_content(self, tenant_slug: str, site_id: str, content_type: str, item_id: str) -> dict | None: ...

    # Hybrid Auth Entities (USER, TUSER, ROLE, PERMISSIONS)
    def get_member_role(self, tenant_slug: str, sub: str) -> str | None: ...
    def list_cognito_members(self, tenant_slug: str) -> list[dict]: ...
    def list_tusers(self, tenant_slug: str) -> list[dict]: ...
    def list_roles(self, tenant_slug: str) -> list[dict]: ...


# --- pure key / item helpers -------------------------------------------------

def _content_type(content_type: str) -> str:
    ct = (content_type or "").upper()
    if ct not in CONTENT_TYPES:
        raise ValueError(f"content_type must be one of {CONTENT_TYPES}, got {content_type!r}")
    return ct


def _content_sk(site_id: str, ct: str, item_id: str) -> str:
    return f"SITE#{site_id}#{ct}#{item_id}"


def _strip(item: dict) -> dict:
    """Drop key/GSI attributes so callers never see storage layout."""
    return {k: v for k, v in item.items() if k not in _KEY_ATTRS}


def _is_legacy_site_row(item: dict) -> bool:
    """Legacy site metadata: sk=SITE#{id} with no second '#' (content rows have one)."""
    sk = item.get("sk", "")
    return sk.startswith("SITE#") and sk.count("#") == 1 and item.get("entity_type", "SITE") == "SITE"


def _site_rows(tenant_slug: str, site_id: str, site: dict) -> tuple[dict, dict]:
    """Build (SITE_META# row, legacy SITE# mirror row). Only the legacy row carries the
    bySiteSlug GSI attrs so the GSI keeps exactly one entry per site during the migration."""
    body = {**_strip(site), "id": site_id, "entity_type": "SITE"}
    pk = pk_tenant(tenant_slug)
    meta = {**body, "pk": pk, "sk": sk_site_meta(site_id)}
    legacy = {**body, "pk": pk, "sk": sk_site(site_id)}
    if body.get("slug"):
        legacy["gsi4pk"] = gsi4pk_slug(body["slug"])
        legacy["gsi4sk"] = gsi4sk_site(site_id)
    return meta, legacy


def _site_out(item: dict) -> dict:
    out = _strip(item)
    sk = item.get("sk", "")
    out["id"] = sk[len(SITE_META_PREFIX):] if sk.startswith(SITE_META_PREFIX) else sk[len("SITE#"):]
    return out


class _StoreBase:
    """Shared logic over four storage primitives implemented per backend."""

    def _get(self, pk: str, sk: str) -> dict | None:
        raise NotImplementedError

    def _put(self, item: dict) -> None:
        raise NotImplementedError

    def _delete(self, pk: str, sk: str) -> dict | None:
        raise NotImplementedError

    def _query_prefix(self, pk: str, sk_prefix: str) -> list[dict]:
        raise NotImplementedError

    # Tenant
    def get_tenant(self, tenant_slug: str) -> dict | None:
        item = self._get(pk_tenant(tenant_slug), sk_tenant())
        return {**_strip(item), "slug": tenant_slug} if item else None

    # Sites
    def list_sites(self, tenant_slug: str) -> list[dict]:
        pk = pk_tenant(tenant_slug)
        rows = {r["sk"][len(SITE_META_PREFIX):]: r for r in self._query_prefix(pk, SITE_META_PREFIX)}
        if self._get(pk, SITE_META_MIGRATION_SK) is None:
            # One-time lazy backfill: the only read of the SITE# range (includes content rows).
            for legacy in self._query_prefix(pk, "SITE#"):
                if not _is_legacy_site_row(legacy):
                    continue
                site_id = legacy["sk"][len("SITE#"):]
                if site_id not in rows:
                    meta = {**legacy, "id": site_id, "entity_type": "SITE", "sk": sk_site_meta(site_id)}
                    for gsi in ("gsi4pk", "gsi4sk"):
                        meta.pop(gsi, None)
                    self._put(meta)
                    rows[site_id] = meta
            self._put({"pk": pk, "sk": SITE_META_MIGRATION_SK})
        return [_site_out(rows[site_id]) for site_id in sorted(rows)]

    def get_site(self, tenant_slug: str, site_id: str) -> dict | None:
        pk = pk_tenant(tenant_slug)
        item = self._get(pk, sk_site_meta(site_id))
        if item is None:
            legacy = self._get(pk, sk_site(site_id))
            if legacy is None or not _is_legacy_site_row(legacy):
                return None
            item, _ = _site_rows(tenant_slug, site_id, legacy)
            self._put(item)  # lazy backfill
        return _site_out(item)

    def put_site(self, tenant_slug: str, site: dict) -> dict:
        site_id = site.get("id") or str(uuid.uuid4())
        meta, legacy = _site_rows(tenant_slug, site_id, site)
        self._put(meta)
        self._put(legacy)
        return _site_out(meta)

    def delete_site_cascade(self, tenant_slug: str, site_id: str) -> None:
        pk = pk_tenant(tenant_slug)
        for row in self._query_prefix(pk, f"SITE#{site_id}#"):
            self._delete(pk, row["sk"])
        self._delete(pk, sk_site(site_id))
        self._delete(pk, sk_site_meta(site_id))

    # Content
    def list_content(self, tenant_slug: str, site_id: str, content_type: str, status: str | None = None) -> list[dict]:
        ct = _content_type(content_type)
        items = [_strip(i) for i in self._query_prefix(pk_tenant(tenant_slug), f"SITE#{site_id}#{ct}#")]
        if status is not None:
            items = [i for i in items if str(i.get("status", "")).upper() == status.upper()]
        return items

    def get_content(self, tenant_slug: str, site_id: str, content_type: str, item_id: str) -> dict | None:
        item = self._get(pk_tenant(tenant_slug), _content_sk(site_id, _content_type(content_type), item_id))
        return _strip(item) if item else None

    def put_content(self, tenant_slug: str, site_id: str, content_type: str, item: dict) -> dict:
        ct = _content_type(content_type)
        body = _strip(item)
        if ct == "PAGE":
            if not body.get("path"):
                raise ValueError("PAGE content requires 'path'")
            item_id = body["path"]
        else:
            item_id = body.setdefault("id", str(uuid.uuid4()))
        self._put({**body, "pk": pk_tenant(tenant_slug), "sk": _content_sk(site_id, ct, item_id)})
        return body

    def delete_content(self, tenant_slug: str, site_id: str, content_type: str, item_id: str) -> dict | None:
        old = self._delete(pk_tenant(tenant_slug), _content_sk(site_id, _content_type(content_type), item_id))
        return _strip(old) if old else None

    # Hybrid auth entities
    def get_member_role(self, tenant_slug: str, sub: str) -> str | None:
        item = self._get(pk_tenant(tenant_slug), sk_user_profile(sub))
        return (item.get("role") or "member").lower() if item else None

    def list_cognito_members(self, tenant_slug: str) -> list[dict]:
        rows = self._query_prefix(pk_tenant(tenant_slug), "USER#")
        return [_strip(r) for r in rows if r["sk"].endswith("#PROFILE")]

    def list_tusers(self, tenant_slug: str) -> list[dict]:
        rows = self._query_prefix(pk_tenant(tenant_slug), "TUSER#")
        return [{k: v for k, v in _strip(r).items() if k != "password_hash"} for r in rows]

    def list_roles(self, tenant_slug: str) -> list[dict]:
        return [_strip(r) for r in self._query_prefix(pk_tenant(tenant_slug), "ROLE#")]


class DynamoDBTenantStore(_StoreBase):
    """boto3-backed store over the 9host-main table."""

    def __init__(self, table=None):
        if table is None:
            table = boto3.resource("dynamodb").Table(os.environ.get("DYNAMODB_TABLE", "9host-main"))
        self.table = table

    def _get(self, pk: str, sk: str) -> dict | None:
        return self.table.get_item(Key={"pk": pk, "sk": sk}).get("Item")

    def _put(self, item: dict) -> None:
        self.table.put_item(Item=item)

    def _delete(self, pk: str, sk: str) -> dict | None:
        return self.table.delete_item(Key={"pk": pk, "sk": sk}, ReturnValues="ALL_OLD").get("Attributes")

    def _query(self, **kwargs: Any) -> list[dict]:
        resp = self.table.query(**kwargs)
        items = resp.get("Items", [])
        while "LastEvaluatedKey" in resp:
            resp = self.table.query(**kwargs, ExclusiveStartKey=resp["LastEvaluatedKey"])
            items.extend(resp.get("Items", []))
        return items

    def _query_prefix(self, pk: str, sk_prefix: str) -> list[dict]:
        assert pk.startswith("TENANT#"), "tenant isolation: partition key must start with TENANT#"
        return self._query(KeyConditionExpression=Key("pk").eq(pk) & Key("sk").begins_with(sk_prefix))

    def update_tenant(self, tenant_slug: str, updates: dict) -> dict:
        updates = {k: v for k, v in updates.items() if k not in _KEY_ATTRS}
        if not updates:
            tenant = self.get_tenant(tenant_slug)
            if tenant is None:
                raise KeyError(tenant_slug)
            return tenant
        names = {f"#k{i}": k for i, k in enumerate(updates)}
        values = {f":v{i}": v for i, v in enumerate(updates.values())}
        try:
            resp = self.table.update_item(
                Key={"pk": pk_tenant(tenant_slug), "sk": sk_tenant()},
                UpdateExpression="SET " + ", ".join(f"#k{i} = :v{i}" for i in range(len(updates))),
                ConditionExpression="attribute_exists(pk)",
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW",
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise KeyError(tenant_slug) from e
            raise
        return {**_strip(resp["Attributes"]), "slug": tenant_slug}

    def adjust_storage_bytes(self, tenant_slug: str, delta_bytes: int) -> int:
        key = {"pk": pk_tenant(tenant_slug), "sk": sk_tenant()}
        delta = int(delta_bytes)
        if delta >= 0:
            resp = self.table.update_item(
                Key=key,
                UpdateExpression="ADD storage_used_bytes :delta",
                ExpressionAttributeValues={":delta": delta},
                ReturnValues="UPDATED_NEW",
            )
            return int(resp["Attributes"]["storage_used_bytes"])
        try:
            resp = self.table.update_item(
                Key=key,
                UpdateExpression="SET storage_used_bytes = storage_used_bytes - :abs_delta",
                ConditionExpression="storage_used_bytes >= :abs_delta",
                ExpressionAttributeValues={":abs_delta": -delta},
                ReturnValues="UPDATED_NEW",
            )
            return int(resp["Attributes"]["storage_used_bytes"])
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
        self.table.update_item(
            Key=key,
            UpdateExpression="SET storage_used_bytes = :zero",
            ExpressionAttributeValues={":zero": 0},
        )
        return 0

    def resolve_site_slug(self, site_slug: str) -> dict | None:
        slug = (site_slug or "").strip().lower()
        if not slug:
            return None
        for item in self._query(**query_by_site_slug(slug)):
            pk, gsk = item.get("pk", ""), item.get("gsi4sk", "")
            if pk.startswith("TENANT#") and gsk.startswith("SITE#"):
                return {"tenant_slug": pk[len("TENANT#"):], "site_id": gsk[len("SITE#"):]}
        return None


class InMemoryTenantStore(_StoreBase):
    """Zero-AWS store for tests. Same key layout as DynamoDB, held in a dict."""

    def __init__(self):
        self.items: dict[tuple[str, str], dict] = {}

    def _get(self, pk: str, sk: str) -> dict | None:
        item = self.items.get((pk, sk))
        return dict(item) if item else None

    def _put(self, item: dict) -> None:
        self.items[(item["pk"], item["sk"])] = dict(item)

    def _delete(self, pk: str, sk: str) -> dict | None:
        return self.items.pop((pk, sk), None)

    def _query_prefix(self, pk: str, sk_prefix: str) -> list[dict]:
        assert pk.startswith("TENANT#"), "tenant isolation: partition key must start with TENANT#"
        return [dict(v) for (p, s), v in sorted(self.items.items()) if p == pk and s.startswith(sk_prefix)]

    def update_tenant(self, tenant_slug: str, updates: dict) -> dict:
        item = self.items.get((pk_tenant(tenant_slug), sk_tenant()))
        if item is None:
            raise KeyError(tenant_slug)
        item.update({k: v for k, v in updates.items() if k not in _KEY_ATTRS})
        return {**_strip(item), "slug": tenant_slug}

    def adjust_storage_bytes(self, tenant_slug: str, delta_bytes: int) -> int:
        pk, sk = pk_tenant(tenant_slug), sk_tenant()
        item = self.items.setdefault((pk, sk), {"pk": pk, "sk": sk})  # ADD upserts, like DynamoDB
        item["storage_used_bytes"] = max(int(item.get("storage_used_bytes") or 0) + int(delta_bytes), 0)
        return item["storage_used_bytes"]

    def resolve_site_slug(self, site_slug: str) -> dict | None:
        slug = (site_slug or "").strip().lower()
        if not slug:
            return None
        for (pk, _), item in sorted(self.items.items()):
            if item.get("gsi4pk") == gsi4pk_slug(slug) and str(item.get("gsi4sk", "")).startswith("SITE#"):
                return {"tenant_slug": pk[len("TENANT#"):], "site_id": item["gsi4sk"][len("SITE#"):]}
        return None
