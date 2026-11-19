"""
Sites API — GET/POST/PUT/DELETE /api/tenant/sites (also serves /api/admin/tenants/{slug}/sites).

GET /api/tenant/sites/{id}/preview — merge site + template for live preview (Task 1.79).
Query param template={slug} overrides site.template_id.

Site metadata goes exclusively through TenantStore (Bug #3: list_sites never reads content
rows). Host-mapping hygiene: a slug change or delete removes the old {slug}.{domain} KVS key;
delete also tears down the site's custom domains (Cloudflare + KVS + row).
"""

import json
import re
import uuid
from datetime import datetime, timezone

import site_storage
from cloudflare_saas import CloudflareAPIError
from cloudns_helpers import add_site_cname, delete_site_cname
from custom_domain_handler import remove_domain
from blocks import RenderContext, render_doc
from publish_handler import MANAGE_ROLES as PUBLISH_ROLES, _base_domain, load_site
from request_context import RequestContext, respond
from reserved_slugs import is_reserved_slug, reserved_slug_error
from template_schema import presets_from_store
from tenant_store import DynamoDBTenantStore
from tier_config import max_sites, tier_rank

SITE_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
BASE_PATH = "/api/tenant/sites"
MANAGE_ROLES = ("admin", "manager")
EDITORS = ("blocks", "richtext")  # site.editor (ADR-0003 §4); absent = "richtext"


def pinned_template_version(site: dict) -> int | None:
    """The template version a site renders with. Sites applied before T-32a have no pin and stay
    on V0001 (the seed's migration of the pre-versioning template)."""
    if not site.get("template_id"):
        return None
    return int(site.get("template_version") or 1)


def _site_to_response(site: dict, head: dict | None = None) -> dict:
    pinned = pinned_template_version(site)
    published = (head or {}).get("published_version") or 0
    out = {
        "id": site.get("id", ""),
        "name": site.get("name", ""),
        "slug": site.get("slug", ""),
        "status": site.get("status", "draft"),
        "template_id": site.get("template_id"),
        "template_version": pinned,
        "template_update_available": bool(pinned and published > pinned),
        "published_at": site.get("published_at"),
        "published_version": int(site["published_version"]) if site.get("published_version") is not None else None,
        "created_at": site.get("created_at", ""),
        "updated_at": site.get("updated_at", ""),
        "editor": site.get("editor") or "richtext",
    }
    if isinstance(site.get("branding"), dict):
        out["branding"] = site["branding"]
    return out


def _slug_taken(store, slug: str, site_id: str | None = None) -> bool:
    """Tenant and site slugs share one global namespace (Tasks 1.76, 1.77)."""
    if store.get_tenant(slug):
        return True
    hit = store.resolve_site_slug(slug)
    return bool(hit) and hit["site_id"] != site_id


def _head_lookup(store):
    """Memoized template-head lookup for site responses (one GetItem per template per request)."""
    cache: dict = {}

    def head(site: dict) -> dict | None:
        tid = site.get("template_id")
        if tid and tid not in cache:
            cache[tid] = store.get_template(tid)
        return cache.get(tid) if tid else None
    return head


def _template_or_error(store, tenant_slug: str, template_id: str, missing_status: int = 400,
                       allow_deprecated: bool = True):
    """(template, None) or (None, error response). Enforces tenant tier >= template.tier_required;
    deprecated templates can't be newly selected (sites already on them keep working)."""
    template = store.get_template(template_id)
    if not template:
        return None, respond(missing_status, {"error": f"Template not found: {template_id}"})
    if not allow_deprecated and (template.get("deprecated") or template.get("published_version") == 0):
        return None, respond(400, {"error": f"Template {template_id} is not available for new sites."})
    tier = ((store.get_tenant(tenant_slug) or {}).get("tier") or "FREE").upper()
    required = template.get("tier_required", "FREE")
    if tier_rank(tier) < tier_rank(required):
        return None, respond(403, {
            "error": f"Template {template_id} requires {required} tier or higher.",
            "tier_required": required,
            "tenant_tier": tier,
        })
    return template, None


def _create_site(store, tenant_slug: str, body: dict) -> dict:
    name = (body.get("name") or "").strip()
    slug = (body.get("slug") or "").strip().lower()
    status = (body.get("status") or "draft").strip().lower()
    template_id = (body.get("template_id") or "").strip().lower() or None
    if not name:
        return respond(400, {"error": "name is required."})
    if status not in ("draft", "published"):
        status = "draft"
    if not slug:
        slug = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-")) or str(uuid.uuid4())[:8]
    if not SITE_SLUG_PATTERN.match(slug):
        return respond(400, {"error": "slug must be lowercase alphanumeric + hyphen."})
    if is_reserved_slug(slug):
        return respond(400, reserved_slug_error(slug))
    if _slug_taken(store, slug):
        return respond(409, {"error": "Slug is already taken.", "slug": slug})
    tier = ((store.get_tenant(tenant_slug) or {}).get("tier") or "FREE").upper()
    cap = max_sites(tier)
    if cap is not None and len(store.list_sites(tenant_slug)) >= cap:  # SEC-11
        return respond(403, {"error": f"{tier.title()} tier allows {cap} sites.", "upgrade_required": True})
    template = None
    if template_id:
        template, err = _template_or_error(store, tenant_slug, template_id, allow_deprecated=False)
        if err:
            return err

    now = datetime.now(timezone.utc).isoformat()
    # New sites start on the block editor (T-31f); absent editor on older sites stays richtext.
    site = {"name": name, "slug": slug, "status": status, "editor": "blocks", "created_at": now, "updated_at": now}
    if template_id:
        site["template_id"] = template_id
        if template.get("published_version"):
            site["template_version"] = template["published_version"]
    site = store.put_site(tenant_slug, site)
    add_site_cname(slug)
    return respond(201, {"site": _site_to_response(site, template)})


def _seed_preset_pages(store, tenant_slug: str, site_id: str, template_id: str, n: int | None) -> list[str]:
    """Create DRAFT pages from the template version's page_presets for paths the site doesn't
    have yet. Tenant pages are never overwritten. Returns the seeded paths."""
    version = store.get_template_version(template_id, n) if n else None
    presets = presets_from_store((version or {}).get("page_presets"))
    existing = {p.get("path") for p in store.list_content(tenant_slug, site_id, "PAGE")}
    rctx = RenderContext.build(tenant_slug=tenant_slug, site_id=site_id)
    now = datetime.now(timezone.utc).isoformat()
    seeded = []
    for path, doc in sorted(presets.items()):
        if path in existing:
            continue
        title = ((doc.get("root") or {}).get("props") or {}).get("title") or path.replace("-", " ").title()
        store.put_content(tenant_slug, site_id, "PAGE", {
            "path": path, "title": title, "status": "DRAFT", "published_at": None,
            "doc": json.dumps(doc, separators=(",", ":"), ensure_ascii=False, sort_keys=True),
            "body": render_doc(doc, rctx),  # dual-write (ADR-0003 §4)
            "created_at": now, "updated_at": now,
        })
        seeded.append(path)
    return seeded


def _update_site(store, tenant_slug: str, site_id: str, body: dict) -> dict:
    site = store.get_site(tenant_slug, site_id)
    if not site:
        return respond(404, {"error": "Site not found."})
    old_slug = site.get("slug", "")

    if body.get("name") is not None:
        site["name"] = str(body["name"]).strip()
    if body.get("slug") is not None:
        s = str(body["slug"]).strip().lower()
        if not SITE_SLUG_PATTERN.match(s):
            return respond(400, {"error": "slug must be lowercase alphanumeric + hyphen."})
        if s != old_slug and is_reserved_slug(s):  # a legacy site may keep its slug
            return respond(400, reserved_slug_error(s))
        if _slug_taken(store, s, site_id):
            return respond(409, {"error": "Slug is already taken.", "slug": s})
        site["slug"] = s
    if body.get("status") is not None:
        s = str(body["status"]).strip().lower()
        if s in ("draft", "published"):
            site["status"] = s
    applied = None  # newly applied template head
    if "template_id" in body and body["template_id"] is not None:
        tid = (body["template_id"] or "").strip().lower() or None
        if tid and tid != site.get("template_id"):
            applied, err = _template_or_error(store, tenant_slug, tid, allow_deprecated=False)
            if err:
                return err
            site["template_id"] = tid
            site.pop("template_version", None)
            if applied.get("published_version"):
                site["template_version"] = applied["published_version"]
        elif not tid:
            site.pop("template_id", None)
            site.pop("template_version", None)
    if body.get("editor") is not None:
        if body["editor"] not in EDITORS:
            return respond(400, {"error": "editor must be one of: blocks, richtext."})
        site["editor"] = body["editor"]
    if "branding" in body and body["branding"] is not None:  # Task 2.94
        branding = body["branding"]
        clean = {
            k: v for k, v in (branding.items() if isinstance(branding, dict) else [])
            if k in ("logo_s3_key", "primary_color", "font_family") and v is not None
        }
        if clean:
            site["branding"] = clean
        else:
            site.pop("branding", None)

    site["updated_at"] = datetime.now(timezone.utc).isoformat()
    site = store.put_site(tenant_slug, site)
    seeded = []
    if applied and site.get("editor") == "blocks":
        seeded = _seed_preset_pages(store, tenant_slug, site_id, site["template_id"], site.get("template_version"))
    new_slug = site.get("slug", "")
    if old_slug and old_slug != new_slug:
        delete_site_cname(old_slug)
        site_storage.delete_host_mapping(f"{old_slug}.{_base_domain()}")
        if new_slug and site.get("published_version") is not None:
            site_storage.put_host_mapping(f"{new_slug}.{_base_domain()}", tenant_slug, site_id)
    if new_slug and new_slug != old_slug:  # SEC-11: ClouDNS only on an actual slug change
        add_site_cname(new_slug)
    head = applied or (store.get_template(site["template_id"]) if site.get("template_id") else None)
    out = {"site": _site_to_response(site, head)}
    if seeded:
        out["seeded_pages"] = seeded
    return respond(200, out)


def _delete_site(store, tenant_slug: str, site_id: str) -> dict:
    site = store.get_site(tenant_slug, site_id)
    if not site:
        return respond(404, {"error": "Site not found."})
    for row in store.list_domains(tenant_slug):
        if row.get("site_id") != site_id:
            continue
        try:
            remove_domain(store.table, row)  # Cloudflare hostname + KVS key + row
        except CloudflareAPIError as e:  # SEC-21: stop; nothing orphaned, the delete is retryable
            return respond(e.http_status, e.to_response_body())
    site_storage.default_storage().delete_files(tenant_slug, site_id)  # before rows: a failure stays retryable
    store.delete_site_cascade(tenant_slug, site_id)
    slug = site.get("slug", "")
    if slug:
        site_storage.delete_host_mapping(f"{slug}.{_base_domain()}")
        delete_site_cname(slug)
    return respond(204)


def _preview_site(store, tenant_slug: str, site_id: str, template_override: str) -> dict:
    """GET /api/tenant/sites/{id}/preview — site metadata + template components (Task 1.79)."""
    site = store.get_site(tenant_slug, site_id)
    if not site:
        return respond(404, {"error": "Site not found."})
    template_id = template_override.lower() or site.get("template_id")
    if not template_id:
        return respond(400, {"error": "No template for preview. Set template_id on site or use ?template={slug}."})
    if template_override:
        template, err = _template_or_error(store, tenant_slug, template_id, missing_status=404)
        if err:
            return err
    else:
        template = store.get_template(template_id)
        if not template:
            return respond(404, {"error": f"Template not found: {template_id}"})
    return respond(200, {"preview": {
        **_site_to_response(site, template),
        "template_slug": template.get("slug", template_id),
        "template_name": template.get("name", ""),
        "components": template.get("components") or {},
    }})


def sites_handler(ctx: RequestContext) -> dict:
    """GET/POST/PUT/DELETE /api/tenant/sites[/{id}[/preview]]. Writes need admin/manager."""
    tenant_slug, _ = ctx.require_tenant_member()
    store = DynamoDBTenantStore()
    method, path = ctx.method, ctx.path
    parts = path[len(BASE_PATH):].strip("/").split("/") if path.startswith(BASE_PATH) else []
    parts = [p for p in parts if p]
    site_id = parts[0] if parts else None

    if method == "GET":
        head = _head_lookup(store)
        if not parts:
            return respond(200, {"sites": [_site_to_response(s, head(s)) for s in store.list_sites(tenant_slug)]})
        if len(parts) == 2 and parts[1] == "preview":
            return _preview_site(store, tenant_slug, site_id, ctx.query("template") or ctx.query("template_id"))
        site = store.get_site(tenant_slug, site_id) if len(parts) == 1 else None
        return respond(200, {"site": _site_to_response(site, head(site))}) if site else respond(404, {"error": "Site not found."})

    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        return respond(405, {"error": "Method not allowed."})
    ctx.require_tenant_member(MANAGE_ROLES)
    if method == "POST" and not parts:
        return _create_site(store, tenant_slug, ctx.json_body())
    if method in ("PUT", "PATCH") and len(parts) == 1:
        return _update_site(store, tenant_slug, site_id, ctx.json_body())
    if method == "DELETE" and len(parts) == 1:
        return _delete_site(store, tenant_slug, site_id)
    return respond(405, {"error": "Method not allowed."})


def site_template_update_handler(ctx: RequestContext) -> dict:
    """POST /api/tenant/sites/{id}/template-update — "Update to vN": pin the site to its template's
    published version (takes effect on the next publish). Admin/manager."""
    store, tenant_slug, site_id, site = load_site(ctx, "template-update", PUBLISH_ROLES)
    template = store.get_template(site["template_id"]) if site.get("template_id") else None
    if not template or not template.get("published_version"):
        return respond(400, {"error": "Site has no template with a published version."})
    site = store.update_site(tenant_slug, site_id, {
        "template_version": template["published_version"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return respond(200, {"site": _site_to_response(site, template)})
