"""
Superadmin platform templates (Task 1.31; T-32a versioning, ADR-0003 §5). All routes require
ctx.require_superadmin(); all storage goes through TenantStore (TENANT#_platform partition).

GET    /api/admin/templates                          list heads
POST   /api/admin/templates                          create head (no versions yet)
GET    /api/admin/templates/{slug}                   head + versions summary
PUT    /api/admin/templates/{slug}                   update head metadata / deprecated
DELETE /api/admin/templates/{slug}                   refused (409) while any site uses it
GET    /api/admin/templates/{slug}/versions/{n}      one immutable version
POST   /api/admin/templates/{slug}/versions          create draft version V{latest+1}
POST   /api/admin/templates/{slug}/publish           set published_version (existing version only)
POST   /api/admin/templates/{slug}/preview           compile a sample site -> {html} (no S3 write)
POST   /api/admin/templates/{slug}/upgrade-sites     pin every site on {slug} below vN to vN
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from blocks import DocValidationError
from request_context import RequestContext, respond
from site_compiler import _DRAFT_TOKEN_SCRIPT, SiteSnapshot, compile_site
from template_schema import (
    VERSION_FIELDS,
    presets_from_store,
    presets_to_store,
    validate_base_renderer,
    validate_template_slug,
    validate_version,
)
from tenant_store import DynamoDBTenantStore
from tier_config import is_valid_tier

BASE_PATH = "/api/admin/templates"
TIER_ERROR = "tier_required must be FREE, PRO, BUSINESS, or VIP"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _head_out(head: dict) -> dict:
    return {
        "slug": head["slug"],
        "name": head.get("name") or head["slug"],
        "description": head.get("description", ""),
        "tier_required": head.get("tier_required", "FREE"),
        "base_renderer": head.get("base_renderer"),
        "latest_version": head.get("latest_version") or 0,
        "published_version": head.get("published_version"),
        "deprecated": bool(head.get("deprecated")),
        "components": head.get("components") or {},  # pre-T-32a metadata; superseded by page_presets
        "created_at": head.get("created_at"),
        "updated_at": head.get("updated_at"),
    }


def _version_out(v: dict) -> dict:
    return {
        "version": v["version"],
        "schema": v.get("schema"),
        "tokens": v.get("tokens") or {},
        "allowed_blocks": v.get("allowed_blocks") or {},
        "page_presets": presets_from_store(v.get("page_presets")),
        "header": v.get("header") or {},
        "footer": v.get("footer") or {},
        "created_at": v.get("created_at"),
    }


def _invalid(e: DocValidationError) -> dict:
    return respond(400, {"error": e.message, "path": e.path})


def _list(store) -> dict:
    return respond(200, {"templates": [_head_out(h) for h in store.list_templates()]})


def _create(store, body: dict) -> dict:
    slug = body.get("slug") or ""
    err = validate_template_slug(slug)
    if err:
        return respond(400, {"error": err})
    tier = (body.get("tier_required") or "FREE").upper()
    if not is_valid_tier(tier):
        return respond(400, {"error": TIER_ERROR})
    try:
        base_renderer = validate_base_renderer(body.get("base_renderer") or "business-generic")
    except DocValidationError as e:
        return _invalid(e)
    now = _now()
    head = {
        "name": (body.get("name") or slug).strip(), "description": (body.get("description") or "").strip(),
        "tier_required": tier, "base_renderer": base_renderer, "latest_version": 0, "published_version": 0,
        "deprecated": False, "created_at": now, "updated_at": now,
    }
    try:
        head = store.put_template_head(slug, head, create_only=True)
    except KeyError:
        return respond(409, {"error": f"Template already exists: {slug}"})
    return respond(201, {**_head_out(head), "versions": []})


def _get(store, head: dict) -> dict:
    published = head.get("published_version")
    versions = [{"version": v["version"], "created_at": v.get("created_at"), "published": v["version"] == published}
                for v in store.list_template_versions(head["slug"])]
    return respond(200, {**_head_out(head), "versions": versions})


def _update(store, head: dict, body: dict) -> dict:
    updates: dict = {}
    if "name" in body:
        updates["name"] = (body.get("name") or "").strip() or head["slug"]
    if "description" in body:
        updates["description"] = (body.get("description") or "").strip()
    if "tier_required" in body:
        tier = (body.get("tier_required") or "FREE").upper()
        if not is_valid_tier(tier):
            return respond(400, {"error": TIER_ERROR})
        updates["tier_required"] = tier
    if "base_renderer" in body:
        try:
            updates["base_renderer"] = validate_base_renderer(body.get("base_renderer"))
        except DocValidationError as e:
            return _invalid(e)
    if "deprecated" in body:
        if not isinstance(body["deprecated"], bool):
            return respond(400, {"error": "deprecated must be a boolean"})
        updates["deprecated"] = body["deprecated"]
    if not updates:
        return respond(400, {"error": "Provide at least one of: name, description, tier_required, base_renderer, deprecated"})
    updates["updated_at"] = _now()
    return _get(store, store.update_template_head(head["slug"], updates))


def _delete(store, head: dict) -> dict:
    sites = store.list_sites_on_template(head["slug"])
    if sites:
        return respond(409, {"error": f"Template {head['slug']} is used by {len(sites)} site(s); deprecate it instead.",
                             "sites": len(sites)})
    store.delete_template(head["slug"])
    return respond(204)


def _create_version(store, head: dict, body: dict) -> dict:
    """Fields omitted from the body are inherited from the latest version."""
    latest = store.get_template_version(head["slug"], head["latest_version"]) if head.get("latest_version") else None
    if latest:
        base = _version_out(latest)
        body = {**{k: base[k] for k in VERSION_FIELDS}, **body}
    try:
        version = validate_version(body)
    except DocValidationError as e:
        return _invalid(e)
    version["page_presets"] = presets_to_store(version["page_presets"])
    version["created_at"] = _now()
    try:
        n = store.put_template_version(head["slug"], version)
    except KeyError:
        return respond(409, {"error": "Version was created concurrently; retry."})
    return respond(201, _version_out(store.get_template_version(head["slug"], n)))


def _existing_version(store, head: dict, n) -> dict | None:
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        return None
    return store.get_template_version(head["slug"], n)


BAD_VERSION = {"error": "version must be an existing version number"}


def _publish(store, head: dict, body: dict) -> dict:
    n = body.get("version")
    if _existing_version(store, head, n) is None:
        return respond(400, BAD_VERSION)
    return _get(store, store.update_template_head(head["slug"], {"published_version": n, "updated_at": _now()}))


def _upgrade_sites(store, head: dict, body: dict) -> dict:
    """Re-pin sites only; each site picks the new tokens up on its next publish."""
    n = body.get("version", head.get("published_version"))
    if _existing_version(store, head, n) is None:
        return respond(400, BAD_VERSION)
    updated = []
    for site in store.list_sites_on_template(head["slug"]):
        if int(site.get("template_version") or 0) < n:
            try:
                store.update_site(site["tenant_slug"], site["id"], {"template_version": n, "updated_at": _now()})
            except KeyError:
                continue  # deleted meanwhile
            updated.append({"tenant_slug": site["tenant_slug"], "site_id": site["id"]})
    return respond(200, {"version": n, "updated": len(updated), "sites": updated})


# --- preview -----------------------------------------------------------------------------------

_SAMPLE_GENERATED_AT = "2026-01-01T00:00:00+00:00"  # fixed: preview output is deterministic
_SAMPLE_POSTS = [
    {"slug": "hello-world", "title": "Hello world", "excerpt": "Our first post.",
     "body": "<p>This is a sample blog post used to preview the template.</p>"},
    {"slug": "behind-the-scenes", "title": "Behind the scenes", "excerpt": "How we work.",
     "body": "<p>Another sample post with <strong>rich text</strong> and a <a href=\"/about/\">link</a>.</p>"},
]
_SAMPLE_EVENTS = [
    {"title": "Launch party", "event_date": "2026-03-14", "venue": "Main Hall"},
    {"title": "Open studio", "event_date": "2026-04-02", "venue": "Studio B"},
]


def _sample_snapshot(head: dict, version: dict | None) -> SiteSnapshot:
    """Pure in-code sample site: preset pages (or one placeholder page), posts, events, no media."""
    presets = presets_from_store((version or {}).get("page_presets"))
    pages = []
    for path, doc in sorted(presets.items()):
        title = ((doc.get("root") or {}).get("props") or {}).get("title") or path.replace("-", " ").title()
        pages.append({"path": path, "title": title, "body": "", "doc": json.dumps(doc)})
    if not any(p["path"] != "_home" for p in pages):
        pages.append({"path": "about", "title": "About", "body": "<p>A sample page for the template preview.</p>"})
    return SiteSnapshot(
        tenant_slug="_preview", site_id="sample",
        site={"name": "Sample Site", "slug": "sample", "editor": "blocks"},
        template={"slug": head["slug"], "base_renderer": head.get("base_renderer") or head["slug"],
                  "tokens": (version or {}).get("tokens") or {}},
        pages=pages, posts=list(_SAMPLE_POSTS), events=list(_SAMPLE_EVENTS), media=[],
        generated_at=_SAMPLE_GENERATED_AT,
    )


def _preview(store, head: dict, body: dict) -> dict:
    """Default version: published, else latest; a template with no versions previews bare."""
    n = body.get("version", head.get("published_version") or head.get("latest_version") or None)
    version = None if n is None else _existing_version(store, head, n)
    if n is not None and version is None:
        return respond(400, BAD_VERSION)
    preset = body.get("preset") or "_home"
    if not isinstance(preset, str):
        return respond(400, {"error": "preset must be a page path"})
    bundle = compile_site(_sample_snapshot(head, version), mode="draft")
    path = "index.html" if preset == "_home" else f"{preset}/index.html"
    if path not in bundle.files:
        return respond(404, {"error": f"No page for preset: {preset}"})
    # CSS is already inlined in draft mode; drop the token-propagation script (srcdoc has no token).
    html = bundle.files[path].decode("utf-8").replace(_DRAFT_TOKEN_SCRIPT, "")
    return respond(200, {"html": html, "version": n, "preset": preset})


# --- router ------------------------------------------------------------------------------------

_SLUG_ACTIONS = {
    ("POST", "versions"): _create_version,
    ("POST", "publish"): _publish,
    ("POST", "preview"): _preview,
    ("POST", "upgrade-sites"): _upgrade_sites,
}


def admin_templates_handler(ctx: RequestContext) -> dict:
    ctx.require_superadmin()
    if ctx.path != BASE_PATH and not ctx.path.startswith(BASE_PATH + "/"):
        return respond(404, {"error": "Not found"})
    store = DynamoDBTenantStore()
    parts = [p for p in ctx.path[len(BASE_PATH):].split("/") if p]
    method = ctx.method
    if not parts:
        if method == "GET":
            return _list(store)
        if method == "POST":
            return _create(store, ctx.json_body())
        return respond(405, {"error": "Method not allowed."})

    slug = parts[0].lower()
    head = store.get_template(slug)
    if head is None:
        return respond(404, {"error": f"Template not found: {slug}"})
    if len(parts) == 1:
        if method == "GET":
            return _get(store, head)
        if method == "PUT":
            return _update(store, head, ctx.json_body())
        if method == "DELETE":
            return _delete(store, head)
        return respond(405, {"error": "Method not allowed."})
    if len(parts) == 3 and parts[1] == "versions" and method == "GET":
        version = store.get_template_version(slug, int(parts[2])) if parts[2].isdigit() else None
        return respond(200, _version_out(version)) if version else respond(404, {"error": "Version not found."})
    action = _SLUG_ACTIONS.get((method, parts[1])) if len(parts) == 2 else None
    if action is None:
        return respond(404, {"error": "Not found"})
    return action(store, head, ctx.json_body())
