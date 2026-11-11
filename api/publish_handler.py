"""
Site publish API (Task 1.96, 1.109, 1.115; T-04).

POST /api/tenant/sites/{id}/publish — atomic versioned publish.
POST /api/tenant/sites/{id}/draft-publish — draft render to draft/.

Flow: load site content -> SiteSnapshot -> pure compile_site(snapshot, mode)
(site_compiler.py: root-relative links in live mode, /preview in draft, sanitized
rich text) -> SiteStoragePort (site_storage.py: v{N}/ + current/ + current.json).
"""

import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError as BotoClientError

from auth_helpers import require_tenant_admin_or_manager, require_tenant_auth, role_can_upload, role_is_admin_or_manager
from dynamodb_helpers import (
    get_site_item,
    get_template_item,
    get_tenant_item,
    get_tenant_template_item,
)
from middleware import with_tenant
from site_compiler import SiteSnapshot, compile_site
from site_storage import S3_SITES_BUCKET, S3SiteStorageAdapter, SiteStoragePort
from tenant_store import DynamoDBTenantStore
from tier_config import CONTENT_MODULE_KEYS, FEATURE_KEYS, tier_has_feature, tier_has_module

S3_MEDIA_BUCKET = "9host-media"


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_domain() -> str:
    domains = (os.environ.get("DOMAINS") or "echo9.net").split(",")
    return domains[0].strip() or "echo9.net"


def _collect_content(table, tenant_slug: str, site_id: str, published_only: bool = True) -> dict:
    """Fetch site content rows (TENANT#{slug} partition) via TenantStore.

    published_only: True -> only status=PUBLISHED pages/posts/events (media has no lifecycle).
    """
    store = DynamoDBTenantStore(table)
    status = "PUBLISHED" if published_only else None
    pages = [
        {"path": i.get("path", ""), "title": i.get("title", ""), "body": i.get("body", "")}
        for i in store.list_content(tenant_slug, site_id, "PAGE", status)
    ]
    posts = [
        {
            "slug": i.get("slug", ""),
            "title": i.get("title", ""),
            "body": i.get("body", ""),
            "excerpt": i.get("excerpt", ""),
            "featured_image_s3_key": i.get("featured_image_s3_key", ""),
        }
        for i in store.list_content(tenant_slug, site_id, "POST", status)
    ]
    events = [
        {"title": i.get("title", ""), "event_date": i.get("event_date", ""), "venue": i.get("venue", "")}
        for i in store.list_content(tenant_slug, site_id, "EVENT", status)
    ]
    media = [
        {"s3_key": i.get("s3_key", ""), "caption": i.get("caption", "")}
        for i in store.list_content(tenant_slug, site_id, "MEDIA")
    ]
    return {"pages": pages, "posts": posts, "events": events, "media": media}


def _resolve_features(tenant_item: dict) -> dict:
    """Compute resolved_features from tenant tier + module_overrides (Task 1.122)."""
    tier = (tenant_item.get("tier") or "FREE").upper()
    mo = tenant_item.get("module_overrides") or {}
    out = {}
    for fk in FEATURE_KEYS:
        out[fk] = bool(mo[fk]) if fk in mo else tier_has_feature(tier, fk)
    for mk in CONTENT_MODULE_KEYS:
        out[mk] = bool(mo[mk]) if mk in mo else tier_has_module(tier, mk)
    return out


def _build_snapshot(
    table,
    tenant_slug: str,
    site_id: str,
    site_item: dict,
    template_item: dict,
    media_base: str,
    resolved_features: dict | None,
    published_only: bool,
    generated_at: str,
) -> SiteSnapshot:
    """Load content and apply tier gating; everything compile_site needs, frozen."""
    features = resolved_features or {}
    site = dict(site_item)
    if not features.get("branding", True) or not isinstance(site.get("branding"), dict):
        site["branding"] = {}
    content = _collect_content(table, tenant_slug, site_id, published_only=published_only)
    return SiteSnapshot(
        tenant_slug=tenant_slug,
        site_id=site_id,
        site=site,
        template=template_item,
        pages=content["pages"],
        posts=content["posts"] if features.get("updates_blog", True) else [],
        events=content["events"] if features.get("events_shows", True) else [],
        # Media: tier gating is enforced at upload, not at publish
        media=content["media"],
        generated_at=generated_at,
        media_base=media_base,
        base_domain=_base_domain(),
    )


def _publish_site(
    table,
    s3_client,
    tenant_slug: str,
    site_id: str,
    site_item: dict,
    template_item: dict,
    media_base: str,
    resolved_features: dict | None = None,
    storage: SiteStoragePort | None = None,
) -> dict:
    """Compile (live) + versioned upload + Site record update."""
    now = _now()
    snapshot = _build_snapshot(
        table, tenant_slug, site_id, site_item, template_item, media_base, resolved_features,
        published_only=True, generated_at=now,
    )
    bundle = compile_site(snapshot, mode="live")
    storage = storage or S3SiteStorageAdapter(s3_client)
    result = storage.publish(tenant_slug, site_id, bundle, published_at=now)

    site_slug = (site_item.get("slug") or "").strip()
    if site_slug:
        storage.sync_host_mapping(tenant_slug, site_id, [f"{site_slug}.{snapshot.base_domain}"])

    # Site metadata stays on SITE#{id} until T-09 migrates all site-metadata callers together.
    table.update_item(
        Key=get_site_item(tenant_slug, site_id),
        UpdateExpression="SET #status = :status, published_at = :now, published_version = :ver, updated_at = :now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "published", ":now": now, ":ver": result["version"]},
    )
    return result


def _draft_publish_site(
    table,
    s3_client,
    tenant_slug: str,
    site_id: str,
    site_item: dict,
    template_item: dict,
    media_base: str,
    resolved_features: dict | None = None,
    storage: SiteStoragePort | None = None,
) -> dict:
    """Compile (draft, all statuses) and upload to draft/. No versioning."""
    snapshot = _build_snapshot(
        table, tenant_slug, site_id, site_item, template_item, media_base, resolved_features,
        published_only=False, generated_at=_now(),
    )
    bundle = compile_site(snapshot, mode="draft")
    storage = storage or S3SiteStorageAdapter(s3_client)
    return storage.publish_draft(tenant_slug, site_id, bundle)


def _rollback_site(
    table,
    s3_client,
    tenant_slug: str,
    site_id: str,
    version: int,
    storage: SiteStoragePort | None = None,
) -> dict | None:
    """Rollback to v{N} via SiteStoragePort; same signature/return as rollback_handler._rollback_site.
    Returns None when v{N} doesn't exist."""
    storage = storage or S3SiteStorageAdapter(s3_client)
    now = _now()
    result = storage.rollback(tenant_slug, site_id, version, now=now)
    if result is None:
        return None
    table.update_item(
        Key=get_site_item(tenant_slug, site_id),
        UpdateExpression="SET published_version = :ver, updated_at = :now",
        ExpressionAttributeValues={":ver": version, ":now": now},
    )
    return result


@with_tenant
def draft_publish_handler(event: dict, context: dict) -> dict:
    """
    POST /api/tenant/sites/{id}/draft-publish — render draft to S3 draft/ (Task 1.116).
    Admin/manager/editor only.
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(400, {"error": "Missing tenant."})

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    prefix = "/api/tenant/sites/"
    suffix = "/draft-publish"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return _json_response(404, {"error": "Not found."})
    site_id = path[len(prefix) : -len(suffix)].strip("/")
    if not site_id:
        return _json_response(400, {"error": "Missing site_id."})

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

    if is_cognito:
        if not role_can_upload(role):
            return _json_response(403, {"error": "Editor, manager, or admin role required."})
    elif not role_can_upload(role or ""):
        return _json_response(403, {"error": "Editor, manager, or admin role required."})

    site_key = get_site_item(tenant_slug, site_id)
    site_resp = table.get_item(Key=site_key)
    site_item = site_resp.get("Item")
    if not site_item:
        return _json_response(404, {"error": "Site not found."})

    template_id = (site_item.get("template_id") or "").strip().lower()
    if not template_id:
        return _json_response(400, {"error": "Site has no template_id."})

    template_resp = table.get_item(Key=get_tenant_template_item(tenant_slug, template_id))
    template_item = template_resp.get("Item")
    if not template_item:
        template_resp = table.get_item(Key=get_template_item(template_id))
        template_item = template_resp.get("Item")
    if not template_item:
        return _json_response(404, {"error": f"Template not found: {template_id}"})

    tenant_resp = table.get_item(Key=get_tenant_item(tenant_slug))
    tenant_item = tenant_resp.get("Item") or {}
    resolved_features = _resolve_features(tenant_item)

    media_base = os.environ.get("CLOUDFRONT_MEDIA_URL", "/media/")

    try:
        result = _draft_publish_site(
            table, s3_client, tenant_slug, site_id, site_item, template_item, media_base, resolved_features
        )
        return _json_response(200, {"draft": result})
    except BotoClientError as e:
        return _json_response(500, {"error": "Draft publish failed.", "detail": str(e)})


@with_tenant
def publish_handler(event: dict, context: dict) -> dict:
    """
    POST /api/tenant/sites/{id}/publish — publish site (Task 1.96).
    Admin/manager only.
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(400, {"error": "Missing tenant. Use subdomain or X-Tenant-Slug header."})

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    prefix = "/api/tenant/sites/"
    if not path.startswith(prefix) or "/publish" not in path:
        return _json_response(404, {"error": "Not found."})

    rest = path[len(prefix) :].strip("/")
    parts = rest.split("/")
    if len(parts) != 2 or parts[1] != "publish":
        return _json_response(404, {"error": "Not found."})
    site_id = parts[0]
    if not site_id:
        return _json_response(400, {"error": "Missing site_id."})

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

    if is_cognito:
        ok, err = require_tenant_admin_or_manager(table, sub_or_username, tenant_slug, event)
        if not ok:
            return _json_response(403, {"error": err or "Forbidden."})
    elif not role_is_admin_or_manager(role):
        return _json_response(403, {"error": "Admin or manager role required."})

    site_key = get_site_item(tenant_slug, site_id)
    site_resp = table.get_item(Key=site_key)
    site_item = site_resp.get("Item")
    if not site_item:
        return _json_response(404, {"error": "Site not found."})

    template_id = (site_item.get("template_id") or "").strip().lower()
    if not template_id:
        return _json_response(400, {"error": "Site has no template_id. Set a template before publishing."})

    # Resolve template: tenant first, then platform (Task 1.125)
    template_resp = table.get_item(Key=get_tenant_template_item(tenant_slug, template_id))
    template_item = template_resp.get("Item")
    if not template_item:
        template_resp = table.get_item(Key=get_template_item(template_id))
        template_item = template_resp.get("Item")
    if not template_item:
        return _json_response(404, {"error": f"Template not found: {template_id}"})

    tenant_resp = table.get_item(Key=get_tenant_item(tenant_slug))
    tenant_item = tenant_resp.get("Item") or {}
    resolved_features = _resolve_features(tenant_item)

    media_base = os.environ.get("CLOUDFRONT_MEDIA_URL", "/media/")

    try:
        result = _publish_site(
            table, s3_client, tenant_slug, site_id, site_item, template_item, media_base, resolved_features
        )
        return _json_response(200, {"publish": result})
    except BotoClientError as e:
        return _json_response(500, {"error": "Publish failed.", "detail": str(e)})
