"""
Content CRUD API (Task 1.95) — GET/POST/PUT/DELETE
/api/tenant/sites/{site_id}/{pages|posts|events|media}[/{id}] and GET .../media/{id}/url.

Reads require tenant membership; writes require admin/manager or a custom role with
the 'sites' permission (T-15; an impersonating
superadmin is "admin", Bug #5). All rows go through TenantStore. MEDIA create/delete adjusts
tenant storage via TenantStore.adjust_storage_bytes (floor at 0, Bug #4).
"""

import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from middleware import validate_content_status, validate_slug_format
from request_context import RequestContext, respond
from tenant_store import DynamoDBTenantStore

S3_MEDIA_BUCKET = "9host-media"
CONTENT_ROLES = ("admin", "manager")

# Reserved paths/slugs — deny-list for pages and posts (Task 1.95)
RESERVED_PAGE_PATHS = frozenset({
    "admin", "api", "login", "signup", "auth", "signin", "signout", "logout", "register",
    "settings", "billing", "dashboard", "users", "sites", "domains", "modules", "analytics",
    "_next", "static", "assets",
})
RESERVED_POST_SLUGS = RESERVED_PAGE_PATHS

_STAMPS = ("status", "published_at", "created_at", "updated_at")
# url segment -> (content type, singular key, label, response fields, updatable fields)
ENTITIES = {
    "pages": ("PAGE", "page", "Page", ("path", "title", "body") + _STAMPS, ("title", "body", "status")),
    "posts": ("POST", "post", "Post", ("id", "slug", "title", "body") + _STAMPS, ("title", "body", "status")),
    "events": (
        "EVENT", "event", "Event", ("id", "title", "event_date", "venue", "location") + _STAMPS,
        ("title", "event_date", "venue", "location", "status"),
    ),
    "media": (
        "MEDIA", "media", "Media", ("id", "s3_key", "caption", "sort_order") + _STAMPS,
        ("caption", "sort_order", "status"),
    ),
}
_DEFAULTS = {"status": "DRAFT", "published_at": None, "sort_order": None}


def _out(item: dict, fields: tuple[str, ...]) -> dict:
    return {f: item.get(f, _DEFAULTS.get(f, "")) for f in fields}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _apply_fields(item: dict, body: dict, fields: tuple[str, ...]) -> None:
    """Apply body fields with status normalization (Task 1.145)."""
    for field in fields:
        if field not in body:
            continue
        val = body[field]
        if field == "status":
            item["status"] = validate_content_status(val)
            if item["status"] == "PUBLISHED" and not item.get("published_at"):
                item["published_at"] = _now()
        elif field == "sort_order":
            try:
                item["sort_order"] = int(val) if val is not None else None
            except (TypeError, ValueError):
                pass
        else:
            item[field] = val if isinstance(val, str) else str(val)


def _validate_slug(value: str, field: str, reserved: frozenset) -> str | None:
    err = validate_slug_format(value, field)
    if err:
        return err
    return f"Reserved {field}: {value}" if value in reserved else None


def _new_item(store, tenant_slug: str, site_id: str, entity: str, body: dict, s3) -> tuple[dict | None, dict | None]:
    """Build a new content row for POST. Returns (item, None) or (None, error response)."""
    now = _now()
    item = {"status": validate_content_status(body.get("status")), "created_at": now, "updated_at": now}
    if item["status"] == "PUBLISHED":
        item["published_at"] = now

    if entity == "pages":
        path = (body.get("path") or "").strip().lower()
        err = _validate_slug(path, "path", RESERVED_PAGE_PATHS)
        if err:
            return None, respond(400, {"error": err})
        if store.get_content(tenant_slug, site_id, "PAGE", path):
            return None, respond(409, {"error": "Page path already exists."})
        item.update(path=path, title=body.get("title", ""), body=body.get("body", ""))
    elif entity == "posts":
        slug = (body.get("slug") or "").strip().lower() or str(uuid.uuid4())[:8]
        err = _validate_slug(slug, "slug", RESERVED_POST_SLUGS)
        if err:
            return None, respond(400, {"error": err})
        item.update(id=str(uuid.uuid4()), slug=slug, title=body.get("title", ""), body=body.get("body", ""))
    elif entity == "events":
        item.update(
            id=str(uuid.uuid4()), title=body.get("title", ""), event_date=body.get("event_date", ""),
            venue=body.get("venue", ""), location=body.get("location", ""),
        )
    else:  # media
        s3_key = (body.get("s3_key") or "").strip()
        if not s3_key:
            return None, respond(400, {"error": "s3_key is required. Upload via POST /upload-url first."})
        if not s3_key.startswith(f"{tenant_slug}/{site_id}/"):
            return None, respond(400, {"error": "s3_key must start with {tenant}/{site_id}/."})
        try:
            size = s3.head_object(Bucket=S3_MEDIA_BUCKET, Key=s3_key).get("ContentLength", 0) or 0
        except ClientError:
            return None, respond(404, {"error": "S3 object not found. Upload via POST /upload-url first."})
        item.update(id=str(uuid.uuid4()), s3_key=s3_key, caption=body.get("caption", ""), size_bytes=int(size))
        _apply_fields(item, body, ("sort_order",))
    return item, None


def _delete_media(store, s3, tenant_slug: str, site_id: str, item: dict) -> None:
    s3_key = item.get("s3_key", "")
    size = 0
    if s3_key:
        try:
            size = s3.head_object(Bucket=S3_MEDIA_BUCKET, Key=s3_key).get("ContentLength", 0) or 0
        except ClientError:
            size = int(item.get("size_bytes") or 0)
        try:
            s3.delete_object(Bucket=S3_MEDIA_BUCKET, Key=s3_key)
        except ClientError:
            pass  # still delete the row
    store.delete_content(tenant_slug, site_id, "MEDIA", item["id"])
    if size > 0:
        store.adjust_storage_bytes(tenant_slug, -int(size))


def content_handler(ctx: RequestContext) -> dict:
    tenant_slug, _ = ctx.require_tenant_member()
    method = ctx.method
    parts = [p for p in ctx.path[len("/api/tenant/sites/"):].split("/") if p]
    site_id = parts[0] if parts else None
    entity = parts[1].lower() if len(parts) > 1 else None
    item_id = parts[2] if len(parts) > 2 else None
    if not site_id:
        return respond(400, {"error": "Missing site_id."})

    store = DynamoDBTenantStore()
    if not store.get_site(tenant_slug, site_id):
        return respond(404, {"error": "Site not found."})
    if method in ("POST", "PUT", "DELETE"):
        ctx.require_permission("sites", CONTENT_ROLES)
    if entity not in ENTITIES:
        return respond(405, {"error": "Method not allowed."})

    ctype, key, label, fields, updatable = ENTITIES[entity]
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1")) if entity == "media" else None
    is_url = entity == "media" and len(parts) == 4 and parts[3] == "url"
    if len(parts) > 3 and not is_url:
        return respond(405, {"error": "Method not allowed."})

    if method == "GET" and not item_id:
        return respond(200, {entity: [_out(i, fields) for i in store.list_content(tenant_slug, site_id, ctype)]})
    if method == "POST" and not item_id:
        item, err = _new_item(store, tenant_slug, site_id, entity, ctx.json_body(), s3)
        if err:
            return err
        item = store.put_content(tenant_slug, site_id, ctype, item)
        if entity == "media" and item.get("size_bytes"):
            store.adjust_storage_bytes(tenant_slug, item["size_bytes"])
        return respond(201, {key: _out(item, fields)})
    if not item_id or method not in ("GET", "PUT", "DELETE"):
        return respond(405, {"error": "Method not allowed."})

    item = store.get_content(tenant_slug, site_id, ctype, item_id)
    if not item:
        return respond(404, {"error": f"{label} not found."})
    item.setdefault("path" if ctype == "PAGE" else "id", item_id)

    if method == "GET" and is_url:
        if not item.get("s3_key"):
            return respond(404, {"error": "Media has no S3 object."})
        url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": S3_MEDIA_BUCKET, "Key": item["s3_key"]}, ExpiresIn=3600
        )
        return respond(200, {"url": url})
    if method == "GET":
        return respond(200, {key: _out(item, fields)})
    if method == "DELETE":
        if entity == "media":
            _delete_media(store, s3, tenant_slug, site_id, item)
        else:
            store.delete_content(tenant_slug, site_id, ctype, item_id)
        return respond(204)

    body = ctx.json_body()  # PUT
    if entity == "posts" and "slug" in body:
        slug = (body["slug"] or "").strip().lower()
        err = _validate_slug(slug, "slug", RESERVED_POST_SLUGS)
        if err:
            return respond(400, {"error": err})
        item["slug"] = slug
    _apply_fields(item, body, updatable)
    item["updated_at"] = _now()
    store.put_content(tenant_slug, site_id, ctype, item)
    return respond(200, {key: _out(item, fields)})
