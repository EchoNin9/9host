"""
Content CRUD API (Task 1.95).

GET/POST/PUT/DELETE for pages, posts, events, media.
Per-upload size check via upload_url_handler. On MEDIA DELETE: remove S3 + decrement storage.
Reserved slug deny-list for pages and posts.
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError as S3ClientError

from auth_helpers import require_tenant_auth, role_can_upload
from dynamodb_helpers import (
    get_site_item,
    get_tenant_item,
    pk_tenant,
    query_site_content,
    sk_site_event,
    sk_site_media,
    sk_site_page,
    sk_site_post,
)
from middleware import parse_json_body, validate_content_status, validate_slug_format, with_tenant

S3_MEDIA_BUCKET = "9host-media"

# Reserved paths/slugs — deny-list (Task 1.95)
RESERVED_PAGE_PATHS = frozenset(
    {
        "admin",
        "api",
        "login",
        "signup",
        "auth",
        "signin",
        "signout",
        "logout",
        "register",
        "settings",
        "billing",
        "dashboard",
        "users",
        "sites",
        "domains",
        "modules",
        "analytics",
        "_next",
        "static",
        "assets",
    }
)
RESERVED_POST_SLUGS = RESERVED_PAGE_PATHS  # Same deny-list for post slugs

# PAGE path: lowercase alphanumeric + hyphen
PAGE_PATH_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
# POST slug: same
POST_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


class _DecimalEncoder(json.JSONEncoder):
    """Encode DynamoDB Decimal values as int or float for JSON serialization."""
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == int(o) else float(o)
        return super().default(o)


def _json_response(status: int, body: dict, empty_body: bool = False) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": "" if empty_body else json.dumps(body, cls=_DecimalEncoder),
    }


def _parse_body(event: dict) -> dict | None:
    """Delegate to centralized parse_json_body (Task 1.145)."""
    return parse_json_body(event)


def _extract_content_path(path: str, prefix: str) -> tuple[str | None, str | None, str | None]:
    """
    Extract (site_id, entity, id_or_path) from path.
    e.g. /api/tenant/sites/abc/pages/home -> (abc, pages, home)
    e.g. /api/tenant/sites/abc/posts -> (abc, posts, None)
    """
    base = "/api/tenant/sites/"
    if not path.startswith(base):
        return None, None, None
    rest = path[len(base) :].strip("/")
    parts = rest.split("/")
    if len(parts) < 2:
        return None, None, None
    site_id = parts[0]
    entity = parts[1].lower() if len(parts) > 1 else None
    id_or_path = parts[2] if len(parts) > 2 else None
    if entity not in ("pages", "posts", "events", "media"):
        return site_id, None, id_or_path
    return site_id, entity, id_or_path


def _page_to_response(item: dict, site_id: str) -> dict:
    sk = item.get("sk", "")
    path = sk.replace(f"SITE#{site_id}#PAGE#", "") if f"SITE#{site_id}#PAGE#" in sk else ""
    return {
        "path": path,
        "title": item.get("title", ""),
        "body": item.get("body", ""),
        "status": item.get("status", "DRAFT"),
        "published_at": item.get("published_at"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def _post_to_response(item: dict, site_id: str) -> dict:
    sk = item.get("sk", "")
    post_id = sk.replace(f"SITE#{site_id}#POST#", "") if f"SITE#{site_id}#POST#" in sk else ""
    return {
        "id": post_id,
        "slug": item.get("slug", ""),
        "title": item.get("title", ""),
        "body": item.get("body", ""),
        "status": item.get("status", "DRAFT"),
        "published_at": item.get("published_at"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def _event_to_response(item: dict, site_id: str) -> dict:
    sk = item.get("sk", "")
    event_id = sk.replace(f"SITE#{site_id}#EVENT#", "") if f"SITE#{site_id}#EVENT#" in sk else ""
    return {
        "id": event_id,
        "title": item.get("title", ""),
        "event_date": item.get("event_date", ""),
        "venue": item.get("venue", ""),
        "location": item.get("location", ""),
        "status": item.get("status", "DRAFT"),
        "published_at": item.get("published_at"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def _media_to_response(item: dict, site_id: str) -> dict:
    sk = item.get("sk", "")
    media_id = sk.replace(f"SITE#{site_id}#MEDIA#", "") if f"SITE#{site_id}#MEDIA#" in sk else ""
    return {
        "id": media_id,
        "s3_key": item.get("s3_key", ""),
        "caption": item.get("caption", ""),
        "sort_order": item.get("sort_order"),
        "status": item.get("status", "DRAFT"),
        "published_at": item.get("published_at"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def _increment_storage(table, tenant_slug: str, size_bytes: int) -> None:
    """Add size_bytes to tenant storage_used_bytes."""
    key = get_tenant_item(tenant_slug)
    table.update_item(
        Key=key,
        UpdateExpression="SET storage_used_bytes = if_not_exists(storage_used_bytes, :zero) + :delta",
        ExpressionAttributeValues={":delta": size_bytes, ":zero": 0},
    )


def _decrement_storage(table, tenant_slug: str, size_bytes: int) -> None:
    """Subtract size_bytes from tenant storage_used_bytes (floor at 0)."""
    key = get_tenant_item(tenant_slug)
    table.update_item(
        Key=key,
        UpdateExpression="SET storage_used_bytes = greatest(if_not_exists(storage_used_bytes, :zero) - :delta, :zero)",
        ExpressionAttributeValues={":delta": size_bytes, ":zero": 0},
    )


def _apply_content_fields(item: dict, body: dict, fields: tuple[str, ...]) -> None:
    """Apply body fields to a content item, with status normalization (Task 1.145)."""
    for field in fields:
        if field not in body:
            continue
        if field == "status":
            s = validate_content_status(body[field])
            item["status"] = s
            if s == "PUBLISHED" and not item.get("published_at"):
                item["published_at"] = datetime.now(timezone.utc).isoformat()
        elif field == "sort_order":
            try:
                item["sort_order"] = int(body[field]) if body[field] is not None else None
            except (TypeError, ValueError):
                pass
        else:
            item[field] = body[field] if isinstance(body[field], str) else str(body[field])


# --- Pages ---


def _list_pages(table, tenant_slug: str, site_id: str) -> dict:
    params = query_site_content(tenant_slug, site_id, "PAGE")
    resp = table.query(**params)
    pages = [_page_to_response(item, site_id) for item in resp.get("Items", [])]
    return _json_response(200, {"pages": pages})


def _get_page(table, tenant_slug: str, site_id: str, path: str) -> dict:
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_page(site_id, path)}
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Page not found."})
    return _json_response(200, {"page": _page_to_response(item, site_id)})


def _create_page(table, tenant_slug: str, site_id: str, body: dict) -> dict:
    path = (body.get("path") or "").strip().lower()
    err = validate_slug_format(path, "path")
    if err:
        return _json_response(400, {"error": err})
    if path in RESERVED_PAGE_PATHS:
        return _json_response(400, {"error": f"Reserved path: {path}"})

    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_page(site_id, path)}
    if table.get_item(Key=key).get("Item"):
        return _json_response(409, {"error": "Page path already exists."})

    now = datetime.now(timezone.utc).isoformat()
    status = validate_content_status(body.get("status"))

    item = {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_site_page(site_id, path),
        "path": path,
        "title": body.get("title", ""),
        "body": body.get("body", ""),
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    if status == "PUBLISHED":
        item["published_at"] = now

    table.put_item(Item=item)
    return _json_response(201, {"page": _page_to_response(item, site_id)})


def _update_page(table, tenant_slug: str, site_id: str, path: str, body: dict) -> dict:
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_page(site_id, path)}
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Page not found."})

    _apply_content_fields(item, body, ("title", "body", "status"))

    item["updated_at"] = datetime.now(timezone.utc).isoformat()
    table.put_item(Item=item)
    return _json_response(200, {"page": _page_to_response(item, site_id)})


def _delete_page(table, tenant_slug: str, site_id: str, path: str) -> dict:
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_page(site_id, path)}
    if not table.get_item(Key=key).get("Item"):
        return _json_response(404, {"error": "Page not found."})
    table.delete_item(Key=key)
    return _json_response(204, {}, empty_body=True)


# --- Posts ---


def _list_posts(table, tenant_slug: str, site_id: str) -> dict:
    params = query_site_content(tenant_slug, site_id, "POST")
    resp = table.query(**params)
    posts = [_post_to_response(item, site_id) for item in resp.get("Items", [])]
    return _json_response(200, {"posts": posts})


def _get_post(table, tenant_slug: str, site_id: str, post_id: str) -> dict:
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_post(site_id, post_id)}
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Post not found."})
    return _json_response(200, {"post": _post_to_response(item, site_id)})


def _create_post(table, tenant_slug: str, site_id: str, body: dict) -> dict:
    slug = (body.get("slug") or "").strip().lower()
    if not slug:
        slug = str(uuid.uuid4())[:8]
    err = validate_slug_format(slug, "slug")
    if err:
        return _json_response(400, {"error": err})
    if slug in RESERVED_POST_SLUGS:
        return _json_response(400, {"error": f"Reserved slug: {slug}"})

    post_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    status = validate_content_status(body.get("status"))

    item = {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_site_post(site_id, post_id),
        "id": post_id,
        "slug": slug,
        "title": body.get("title", ""),
        "body": body.get("body", ""),
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    if status == "PUBLISHED":
        item["published_at"] = now

    table.put_item(Item=item)
    return _json_response(201, {"post": _post_to_response(item, site_id)})


def _update_post(table, tenant_slug: str, site_id: str, post_id: str, body: dict) -> dict:
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_post(site_id, post_id)}
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Post not found."})

    if "slug" in body:
        s = (body["slug"] or "").strip().lower()
        err = validate_slug_format(s, "slug")
        if err:
            return _json_response(400, {"error": err})
        if s in RESERVED_POST_SLUGS:
            return _json_response(400, {"error": f"Reserved slug: {s}"})
        item["slug"] = s
    _apply_content_fields(item, body, ("title", "body", "status"))

    item["updated_at"] = datetime.now(timezone.utc).isoformat()
    table.put_item(Item=item)
    return _json_response(200, {"post": _post_to_response(item, site_id)})


def _delete_post(table, tenant_slug: str, site_id: str, post_id: str) -> dict:
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_post(site_id, post_id)}
    if not table.get_item(Key=key).get("Item"):
        return _json_response(404, {"error": "Post not found."})
    table.delete_item(Key=key)
    return _json_response(204, {}, empty_body=True)


# --- Events ---


def _list_events(table, tenant_slug: str, site_id: str) -> dict:
    params = query_site_content(tenant_slug, site_id, "EVENT")
    resp = table.query(**params)
    events = [_event_to_response(item, site_id) for item in resp.get("Items", [])]
    return _json_response(200, {"events": events})


def _get_event(table, tenant_slug: str, site_id: str, event_id: str) -> dict:
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_event(site_id, event_id)}
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Event not found."})
    return _json_response(200, {"event": _event_to_response(item, site_id)})


def _create_event(table, tenant_slug: str, site_id: str, body: dict) -> dict:
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    status = validate_content_status(body.get("status"))

    item = {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_site_event(site_id, event_id),
        "id": event_id,
        "title": body.get("title", ""),
        "event_date": body.get("event_date", ""),
        "venue": body.get("venue", ""),
        "location": body.get("location", ""),
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    if status == "PUBLISHED":
        item["published_at"] = now

    table.put_item(Item=item)
    return _json_response(201, {"event": _event_to_response(item, site_id)})


def _update_event(table, tenant_slug: str, site_id: str, event_id: str, body: dict) -> dict:
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_event(site_id, event_id)}
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Event not found."})

    _apply_content_fields(item, body, ("title", "event_date", "venue", "location", "status"))

    item["updated_at"] = datetime.now(timezone.utc).isoformat()
    table.put_item(Item=item)
    return _json_response(200, {"event": _event_to_response(item, site_id)})


def _delete_event(table, tenant_slug: str, site_id: str, event_id: str) -> dict:
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_event(site_id, event_id)}
    if not table.get_item(Key=key).get("Item"):
        return _json_response(404, {"error": "Event not found."})
    table.delete_item(Key=key)
    return _json_response(204, {}, empty_body=True)


# --- Media ---


def _list_media(table, tenant_slug: str, site_id: str) -> dict:
    params = query_site_content(tenant_slug, site_id, "MEDIA")
    resp = table.query(**params)
    media = [_media_to_response(item, site_id) for item in resp.get("Items", [])]
    return _json_response(200, {"media": media})


def _get_media(table, tenant_slug: str, site_id: str, media_id: str) -> dict:
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_media(site_id, media_id)}
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Media not found."})
    return _json_response(200, {"media": _media_to_response(item, site_id)})


def _create_media(table, tenant_slug: str, site_id: str, body: dict, s3_client, region: str) -> dict:
    s3_key = (body.get("s3_key") or "").strip()
    if not s3_key:
        return _json_response(400, {"error": "s3_key is required. Upload via POST /upload-url first."})

    # Validate s3_key belongs to this tenant/site
    prefix = f"{tenant_slug}/{site_id}/"
    if not s3_key.startswith(prefix):
        return _json_response(400, {"error": "s3_key must start with {tenant}/{site_id}/."})

    # Get object size and verify it exists
    try:
        head = s3_client.head_object(Bucket=S3_MEDIA_BUCKET, Key=s3_key)
        size_bytes = head.get("ContentLength", 0) or 0
    except S3ClientError:
        return _json_response(404, {"error": "S3 object not found. Upload via POST /upload-url first."})

    media_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    status = validate_content_status(body.get("status"))

    sort_order = body.get("sort_order")
    if sort_order is not None:
        try:
            sort_order = int(sort_order)
        except (TypeError, ValueError):
            sort_order = None

    item = {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_site_media(site_id, media_id),
        "id": media_id,
        "s3_key": s3_key,
        "caption": body.get("caption", ""),
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    if sort_order is not None:
        item["sort_order"] = sort_order
    if status == "PUBLISHED":
        item["published_at"] = now

    table.put_item(Item=item)
    _increment_storage(table, tenant_slug, size_bytes)

    return _json_response(201, {"media": _media_to_response(item, site_id)})


def _update_media(table, tenant_slug: str, site_id: str, media_id: str, body: dict) -> dict:
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_media(site_id, media_id)}
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Media not found."})

    _apply_content_fields(item, body, ("caption", "sort_order", "status"))

    item["updated_at"] = datetime.now(timezone.utc).isoformat()
    table.put_item(Item=item)
    return _json_response(200, {"media": _media_to_response(item, site_id)})


def _get_media_presigned_url(s3_client, tenant_slug: str, site_id: str, media_id: str, table) -> dict:
    """GET /api/tenant/sites/{id}/media/{id}/url — presigned S3 URL for display."""
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_media(site_id, media_id)}
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Media not found."})
    s3_key = item.get("s3_key", "")
    if not s3_key:
        return _json_response(404, {"error": "Media has no S3 object."})
    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_MEDIA_BUCKET, "Key": s3_key},
            ExpiresIn=3600,
        )
        return _json_response(200, {"url": url})
    except Exception:
        return _json_response(500, {"error": "Failed to generate URL."})


def _delete_media(
    table, tenant_slug: str, site_id: str, media_id: str, s3_client, region: str
) -> dict:
    key = {"pk": pk_tenant(tenant_slug), "sk": sk_site_media(site_id, media_id)}
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Media not found."})

    s3_key = item.get("s3_key", "")
    size_bytes = 0

    if s3_key:
        try:
            head = s3_client.head_object(Bucket=S3_MEDIA_BUCKET, Key=s3_key)
            size_bytes = head.get("ContentLength", 0) or 0
        except S3ClientError:
            pass
        try:
            s3_client.delete_object(Bucket=S3_MEDIA_BUCKET, Key=s3_key)
        except S3ClientError:
            pass  # Still delete DynamoDB record

    table.delete_item(Key=key)
    if size_bytes > 0:
        _decrement_storage(table, tenant_slug, size_bytes)

    return _json_response(204, {}, empty_body=True)


@with_tenant
def content_handler(event: dict, context: dict) -> dict:
    """
    Content CRUD: GET/POST/PUT/DELETE /api/tenant/sites/{site_id}/pages|posts|events|media
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(400, {"error": "Missing tenant. Use subdomain or X-Tenant-Slug header."})

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    region = os.environ.get("AWS_REGION", "us-east-1")
    s3_client = boto3.client("s3", region_name=region)

    auth_result = require_tenant_auth(event, table, tenant_slug, region)
    if auth_result[0] is not True:
        _, err_resp = auth_result
        return _json_response(err_resp.get("statusCode", 401), json.loads(err_resp.get("body", "{}")))
    _, sub_or_username, role, is_cognito = auth_result

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    )

    site_id, entity, id_or_path = _extract_content_path(path, "/api/tenant/sites/")
    if not site_id:
        return _json_response(400, {"error": "Missing site_id."})

    # Verify site exists
    site_key = get_site_item(tenant_slug, site_id)
    if not table.get_item(Key=site_key).get("Item"):
        return _json_response(404, {"error": "Site not found."})

    # POST/PUT/DELETE require admin, manager, or editor (content editing)
    if method in ("POST", "PUT", "DELETE"):
        if is_cognito:
            from auth_helpers import get_user_role_in_tenant

            role_in_tenant = get_user_role_in_tenant(table, sub_or_username, tenant_slug)
            if not role_can_upload(role_in_tenant or ""):
                return _json_response(403, {"error": "Admin, manager, or editor role required."})
        elif not role_can_upload(role):
            return _json_response(403, {"error": "Admin, manager, or editor role required."})

    if entity == "pages":
        if method == "GET" and not id_or_path:
            return _list_pages(table, tenant_slug, site_id)
        if method == "GET" and id_or_path:
            return _get_page(table, tenant_slug, site_id, id_or_path)
        if method == "POST" and not id_or_path:
            return _create_page(table, tenant_slug, site_id, _parse_body(event) or {})
        if method == "PUT" and id_or_path:
            return _update_page(table, tenant_slug, site_id, id_or_path, _parse_body(event) or {})
        if method == "DELETE" and id_or_path:
            return _delete_page(table, tenant_slug, site_id, id_or_path)

    if entity == "posts":
        if method == "GET" and not id_or_path:
            return _list_posts(table, tenant_slug, site_id)
        if method == "GET" and id_or_path:
            return _get_post(table, tenant_slug, site_id, id_or_path)
        if method == "POST" and not id_or_path:
            return _create_post(table, tenant_slug, site_id, _parse_body(event) or {})
        if method == "PUT" and id_or_path:
            return _update_post(table, tenant_slug, site_id, id_or_path, _parse_body(event) or {})
        if method == "DELETE" and id_or_path:
            return _delete_post(table, tenant_slug, site_id, id_or_path)

    if entity == "events":
        if method == "GET" and not id_or_path:
            return _list_events(table, tenant_slug, site_id)
        if method == "GET" and id_or_path:
            return _get_event(table, tenant_slug, site_id, id_or_path)
        if method == "POST" and not id_or_path:
            return _create_event(table, tenant_slug, site_id, _parse_body(event) or {})
        if method == "PUT" and id_or_path:
            return _update_event(table, tenant_slug, site_id, id_or_path, _parse_body(event) or {})
        if method == "DELETE" and id_or_path:
            return _delete_event(table, tenant_slug, site_id, id_or_path)

    if entity == "media":
        path_rstrip = path.rstrip("/")
        if method == "GET" and id_or_path and path_rstrip.endswith("/url"):
            return _get_media_presigned_url(s3_client, tenant_slug, site_id, id_or_path, table)
        if method == "GET" and not id_or_path:
            return _list_media(table, tenant_slug, site_id)
        if method == "GET" and id_or_path:
            return _get_media(table, tenant_slug, site_id, id_or_path)
        if method == "POST" and not id_or_path:
            return _create_media(table, tenant_slug, site_id, _parse_body(event) or {}, s3_client, region)
        if method == "PUT" and id_or_path:
            return _update_media(table, tenant_slug, site_id, id_or_path, _parse_body(event) or {})
        if method == "DELETE" and id_or_path:
            return _delete_media(table, tenant_slug, site_id, id_or_path, s3_client, region)

    return _json_response(405, {"error": "Method not allowed."})
