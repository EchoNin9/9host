"""
Domains API — GET/POST/DELETE /api/tenant/domains[/{domain}[/activate]]
(also serves /api/admin/tenants/{slug}/domains).

Custom domains require the ``custom_domains`` feature (Pro+ tier or module override); an
impersonating superadmin bypasses the tier gate. Domains are Cloudflare for SaaS custom
hostnames (``CNAME -> proxy.echonin9.com``) managed through ``custom_domain_handler``, which keeps
Cloudflare, HostMappingKVS and the DOMAIN# row in sync.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from cloudflare_saas import CloudflareAPIError, InvalidDomainError, validate_domain
from custom_domain_handler import STATUS_ACTIVE, domain_to_response, refresh_domain_status, register_domain, remove_domain
from request_context import HttpError, RequestContext, respond
from tenant_store import DynamoDBTenantStore

BASE_PATH = "/api/tenant/domains"
MANAGE_ROLES = ("admin", "manager")
REFRESH_MIN_INTERVAL = timedelta(seconds=30)  # per-row Cloudflare status-poll throttle (T-18)


def _cf_error(err: CloudflareAPIError) -> dict:
    return respond(err.http_status, err.to_response_body())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _checked_recently(item: dict, now: datetime) -> bool:
    """True if Cloudflare was polled for this row less than REFRESH_MIN_INTERVAL ago."""
    raw = item.get("last_checked_at")
    if not raw:
        return False
    try:
        last = datetime.fromisoformat(str(raw))
    except ValueError:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return timedelta(0) <= now - last < REFRESH_MIN_INTERVAL


def _refresh_pending(table, items: list[dict]) -> list[dict]:
    """Poll Cloudflare for non-ACTIVE domains (best-effort; errors keep stored status).

    The UI polls every 10 s, so a row checked within REFRESH_MIN_INTERVAL is served from
    DynamoDB as-is (T-18). ``POST .../activate`` always re-checks.
    """
    now = _utcnow()
    for item in items:
        if (item.get("status") or "").upper() == STATUS_ACTIVE and item.get("cf_hostname_id"):
            continue
        if _checked_recently(item, now):
            continue
        refresh_domain_status(table, item)
    return items


def _create_domain(store, tenant_slug: str, body: dict) -> dict:
    site_id = (body.get("site_id") or "").strip()
    if not (body.get("domain") or "").strip():
        return respond(400, {"error": "domain is required."})
    if not site_id:
        return respond(400, {"error": "site_id is required."})
    try:
        domain = validate_domain(body.get("domain"))
    except InvalidDomainError as e:
        return respond(400, {"error": str(e)})
    if store.get_site(tenant_slug, site_id) is None:
        return respond(404, {"error": "Site not found."})
    if store.get_domain(tenant_slug, domain):
        return respond(409, {"error": "Domain already exists for this tenant."})
    if store.domain_owner(domain):
        return respond(409, {"error": "Domain is already in use by another site."})
    try:
        out = domain_to_response(register_domain(store.table, tenant_slug, domain, site_id))
    except CloudflareAPIError as e:
        return _cf_error(e)
    return respond(201, {"domain": out, "message": f"Add a CNAME record pointing {domain} to {out['cname_target']}."})


def _activate_domain(store, item: dict, domain: str) -> dict:
    """Re-check Cloudflare status now (registers legacy rows lacking cf_hostname_id)."""
    if (item.get("status") or "").upper() == STATUS_ACTIVE and item.get("cf_hostname_id"):
        return respond(400, {"error": "Domain already ACTIVE. No activation needed."})
    try:
        refresh_domain_status(store.table, item, raise_errors=True)
    except CloudflareAPIError as e:
        return _cf_error(e)
    out = domain_to_response(item)
    if out["status"] == STATUS_ACTIVE:
        message = "Domain is active."
    else:
        message = (
            f"Point a CNAME for {domain} to {out['cname_target']}. If you cannot use a CNAME "
            "(apex domain), add the TXT validation records. SSL is issued automatically once verified."
        )
    return respond(200, {
        "domain": out,
        "validation_records": out["validation_records"],
        "acm_validation_records": out["validation_records"],
        "message": message,
    })


def domains_handler(ctx: RequestContext) -> dict:
    tenant_slug, _ = ctx.require_tenant_member()
    if not ctx.is_impersonating:
        try:
            ctx.require_feature("custom_domains")
        except HttpError:
            tier = ((ctx.tenant_item or {}).get("tier") or "FREE").upper()
            return respond(403, {
                "error": "Custom Domains requires Pro, Business, or VIP tier.", "tier": tier, "upgrade_required": True,
            })
    store = DynamoDBTenantStore()
    method = ctx.method
    parts = [p for p in ctx.path[len(BASE_PATH):].split("/") if p]
    domain = unquote(parts[0]).lower() if parts else None
    suffix = "/".join(parts[1:])

    if method == "GET" and not domain:
        items = _refresh_pending(store.table, store.list_domains(tenant_slug))
        return respond(200, {"domains": [domain_to_response(i) for i in items]})
    if method == "GET" and not suffix:
        item = store.get_domain(tenant_slug, domain)
        if not item:
            return respond(404, {"error": "Domain not found."})
        return respond(200, {"domain": domain_to_response(_refresh_pending(store.table, [item])[0])})

    if method not in ("POST", "DELETE"):
        return respond(405, {"error": "Method not allowed."})
    ctx.require_permission("domains", MANAGE_ROLES)
    if method == "POST" and not domain:
        return _create_domain(store, tenant_slug, ctx.json_body())
    item = store.get_domain(tenant_slug, domain) if domain else None
    if method == "DELETE" and domain and not suffix:
        if not item:
            return respond(404, {"error": "Domain not found."})
        try:
            remove_domain(store.table, item)
        except CloudflareAPIError as e:
            return _cf_error(e)
        return respond(204)
    if method == "POST" and suffix == "activate":
        if not item:
            return respond(404, {"error": "Domain not found."})
        return _activate_domain(store, item, domain)
    return respond(405, {"error": "Method not allowed."})
