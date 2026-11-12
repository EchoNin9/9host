"""
Sites API — GET/POST/PUT/DELETE /api/tenant/sites (also serves /api/admin/tenants/{slug}/sites).

GET /api/tenant/sites/{id}/preview — merge site + template for live preview (Task 1.79).
Query param template={slug} overrides site.template_id.

Site metadata goes exclusively through TenantStore (Bug #3: list_sites never reads content
rows). Host-mapping hygiene: a slug change or delete removes the old {slug}.{domain} KVS key;
delete also tears down the site's custom domains (Cloudflare + KVS + row).
"""

import re
import uuid
from datetime import datetime, timezone

import site_storage
from cloudflare_saas import CloudflareAPIError
from cloudns_helpers import add_site_cname, delete_site_cname
from custom_domain_handler import remove_domain
from publish_handler import _base_domain
from request_context import RequestContext, respond
from tenant_store import DynamoDBTenantStore
from tier_config import tier_rank

SITE_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
BASE_PATH = "/api/tenant/sites"
MANAGE_ROLES = ("admin", "manager")


def _site_to_response(site: dict) -> dict:
    out = {
        "id": site.get("id", ""),
        "name": site.get("name", ""),
        "slug": site.get("slug", ""),
        "status": site.get("status", "draft"),
        "template_id": site.get("template_id"),
        "published_at": site.get("published_at"),
        "published_version": int(site["published_version"]) if site.get("published_version") is not None else None,
        "created_at": site.get("created_at", ""),
        "updated_at": site.get("updated_at", ""),
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


def _template_or_error(store, tenant_slug: str, template_id: str, missing_status: int = 400):
    """(template, None) or (None, error response). Enforces tenant tier >= template.tier_required."""
    template = store.get_template(template_id)
    if not template:
        return None, respond(missing_status, {"error": f"Template not found: {template_id}"})
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
    if _slug_taken(store, slug):
        return respond(409, {"error": "Slug is already taken.", "slug": slug})
    if template_id:
        _, err = _template_or_error(store, tenant_slug, template_id)
        if err:
            return err

    now = datetime.now(timezone.utc).isoformat()
    site = {"name": name, "slug": slug, "status": status, "created_at": now, "updated_at": now}
    if template_id:
        site["template_id"] = template_id
    site = store.put_site(tenant_slug, site)
    add_site_cname(slug)
    return respond(201, {"site": _site_to_response(site)})


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
        if _slug_taken(store, s, site_id):
            return respond(409, {"error": "Slug is already taken.", "slug": s})
        site["slug"] = s
    if body.get("status") is not None:
        s = str(body["status"]).strip().lower()
        if s in ("draft", "published"):
            site["status"] = s
    if "template_id" in body and body["template_id"] is not None:
        tid = (body["template_id"] or "").strip().lower() or None
        if tid:
            _, err = _template_or_error(store, tenant_slug, tid)
            if err:
                return err
            site["template_id"] = tid
        else:
            site.pop("template_id", None)
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
    new_slug = site.get("slug", "")
    if old_slug and old_slug != new_slug:
        delete_site_cname(old_slug)
        site_storage.delete_host_mapping(f"{old_slug}.{_base_domain()}")
        if new_slug and site.get("published_version") is not None:
            site_storage.put_host_mapping(f"{new_slug}.{_base_domain()}", tenant_slug, site_id)
    if new_slug:
        add_site_cname(new_slug)
    return respond(200, {"site": _site_to_response(site)})


def _delete_site(store, tenant_slug: str, site_id: str) -> dict:
    site = store.get_site(tenant_slug, site_id)
    if not site:
        return respond(404, {"error": "Site not found."})
    for row in store.list_domains(tenant_slug):
        if row.get("site_id") != site_id:
            continue
        try:
            remove_domain(store.table, row)  # Cloudflare hostname + KVS key + row
        except CloudflareAPIError:
            site_storage.delete_host_mapping(row["sk"][len("DOMAIN#"):])  # row kept for retry
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
        **_site_to_response(site),
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
        if not parts:
            return respond(200, {"sites": [_site_to_response(s) for s in store.list_sites(tenant_slug)]})
        if len(parts) == 2 and parts[1] == "preview":
            return _preview_site(store, tenant_slug, site_id, ctx.query("template") or ctx.query("template_id"))
        site = store.get_site(tenant_slug, site_id) if len(parts) == 1 else None
        return respond(200, {"site": _site_to_response(site)}) if site else respond(404, {"error": "Site not found."})

    if method not in ("POST", "PUT", "DELETE"):
        return respond(405, {"error": "Method not allowed."})
    ctx.require_tenant_member(MANAGE_ROLES)
    if method == "POST" and not parts:
        return _create_site(store, tenant_slug, ctx.json_body())
    if method == "PUT" and len(parts) == 1:
        return _update_site(store, tenant_slug, site_id, ctx.json_body())
    if method == "DELETE" and len(parts) == 1:
        return _delete_site(store, tenant_slug, site_id)
    return respond(405, {"error": "Method not allowed."})
