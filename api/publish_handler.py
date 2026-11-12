"""
Site publish API (Task 1.96, 1.109, 1.115; T-04).

POST /api/tenant/sites/{id}/publish — atomic versioned publish (admin/manager).
POST /api/tenant/sites/{id}/draft-publish — draft render to draft/ (admin/manager/editor).

Flow: load site content -> SiteSnapshot -> pure compile_site(snapshot, mode)
(site_compiler.py: root-relative links in live mode, /preview in draft, sanitized
rich text) -> SiteStoragePort (site_storage.py: v{N}/ + current/ + current.json).
Site metadata is read and written only through TenantStore (Bug #3).
"""

import os
from datetime import datetime, timezone

from request_context import HttpError, RequestContext, respond
from site_compiler import SiteSnapshot, compile_site
from site_storage import S3SiteStorageAdapter, SiteStoragePort
from tenant_store import DynamoDBTenantStore
from tier_config import CONTENT_MODULE_KEYS, FEATURE_KEYS, tier_has_feature, tier_has_module

MANAGE_ROLES = ("admin", "manager")
CONTENT_ROLES = ("admin", "manager", "editor")


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


def _active_custom_domains(store, tenant_slug: str, site_id: str) -> list[str]:
    """ACTIVE custom domains (TENANT#{slug} / DOMAIN#{domain}) bound to this site, for HostMappingKVS."""
    return [
        row["sk"][len("DOMAIN#"):]
        for row in store.list_domains(tenant_slug)
        if row.get("site_id") == site_id and (row.get("status") or "").upper() == "ACTIVE"
    ]


def _update_site(store, tenant_slug: str, site_id: str, **fields) -> None:
    """Field-level, atomic site metadata update (SITE_META# + SITE# mirror; T-14).
    A site deleted concurrently is left deleted."""
    try:
        store.update_site(tenant_slug, site_id, fields)
    except KeyError:
        pass


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
    hostnames = [f"{site_slug}.{snapshot.base_domain}"] if site_slug else []
    store = DynamoDBTenantStore(table)
    hostnames += _active_custom_domains(store, tenant_slug, site_id)
    if hostnames:
        storage.sync_host_mapping(tenant_slug, site_id, hostnames)  # best-effort: never fails a publish
    _update_site(
        store, tenant_slug, site_id,
        status="published", published_at=now, published_version=result["version"], updated_at=now,
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
    """Rollback to v{N} via SiteStoragePort. Returns None when v{N} doesn't exist."""
    storage = storage or S3SiteStorageAdapter(s3_client)
    now = _now()
    result = storage.rollback(tenant_slug, site_id, version, now=now)
    if result is None:
        return None
    _update_site(DynamoDBTenantStore(table), tenant_slug, site_id, published_version=version, updated_at=now)
    return result


def load_site(ctx: RequestContext, action: str, roles: tuple[str, ...]):
    """Shared prelude for /api/tenant/sites/{id}/{action}: role check + site lookup.
    Returns (store, tenant_slug, site_id, site); raises HttpError (401/403/404)."""
    tenant_slug, _ = ctx.require_tenant_member(roles)
    parts = [p for p in ctx.path[len("/api/tenant/sites/"):].split("/") if p]
    if len(parts) != 2 or parts[1] != action:
        raise HttpError(404, "Not found.")
    store = DynamoDBTenantStore()
    site = store.get_site(tenant_slug, parts[0])
    if not site:
        raise HttpError(404, "Site not found.")
    return store, tenant_slug, parts[0], site


def _compile_inputs(store, tenant_slug: str, site: dict) -> tuple[dict, dict, str]:
    """(template, resolved_features, media_base); template resolved tenant-first (Task 1.125)."""
    template_id = (site.get("template_id") or "").strip().lower()
    if not template_id:
        raise HttpError(400, "Site has no template_id. Set a template before publishing.")
    template = store.get_template(template_id, tenant_slug)
    if not template:
        raise HttpError(404, f"Template not found: {template_id}")
    features = _resolve_features(store.get_tenant(tenant_slug) or {})
    return template, features, os.environ.get("CLOUDFRONT_MEDIA_URL", "/media/")


def draft_publish_handler(ctx: RequestContext) -> dict:
    """POST /api/tenant/sites/{id}/draft-publish — render draft to S3 draft/ (Task 1.116)."""
    store, tenant_slug, site_id, site = load_site(ctx, "draft-publish", CONTENT_ROLES)
    template, features, media_base = _compile_inputs(store, tenant_slug, site)
    result = _draft_publish_site(store.table, _s3(), tenant_slug, site_id, site, template, media_base, features)
    return respond(200, {"draft": result})


def publish_handler(ctx: RequestContext) -> dict:
    """POST /api/tenant/sites/{id}/publish — publish site (Task 1.96)."""
    store, tenant_slug, site_id, site = load_site(ctx, "publish", MANAGE_ROLES)
    template, features, media_base = _compile_inputs(store, tenant_slug, site)
    result = _publish_site(store.table, _s3(), tenant_slug, site_id, site, template, media_base, features)
    return respond(200, {"publish": result})


def _s3():
    import boto3

    return boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
