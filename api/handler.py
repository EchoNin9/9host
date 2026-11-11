"""
9host API Lambda handler — main entry point for API Gateway (HTTP API v2 proxy).

Dispatches requests via a declarative route registry. Migrated handlers take a
``RequestContext`` (auth, tenant, effective role resolved once) and run inside
``run_with_context``; legacy ``(event, context)`` handlers are called directly. Everything
is wrapped in the safe error boundary (Bug #8: no tracebacks in 500s).

``/api/admin/tenants/{slug}/{sites|domains|users|tusers|roles}`` reuse the tenant handlers
with an admin-impersonated RequestContext (superadmin only).
"""

import dataclasses

from admin_handler import (
    create_tenant_handler,
    delete_tenant_handler,
    edge_kvs_handler,
    get_tenant_by_slug_handler,
    list_all_tenants_handler,
    patch_tenant_handler as admin_patch_tenant_handler,
)
from admin_templates_handler import (
    create_template_handler,
    delete_template_handler,
    get_template_handler,
    list_templates_handler,
    update_template_handler,
)
from admin_users_handler import admin_stats_handler, admin_users_handler as admin_global_users_handler
from analytics_handler import get_analytics_handler
from billing_handler import billing_checkout_handler, billing_portal_handler
from content_handler import ENTITIES as CONTENT_ENTITIES, content_handler
from domains_handler import domains_handler
from draft_handler import draft_token_handler
from handler_example import get_tenant_handler, patch_tenant_handler, put_tenant_handler
from publish_handler import draft_publish_handler, publish_handler
from request_context import (
    CORS_HEADERS,
    RequestContext,
    finalize_response,
    internal_error_response,
    respond,
    run_with_context,
)
from roles_handler import roles_handler
from rollback_handler import rollback_handler
from site_auth_handler import site_login_handler
from sites_handler import sites_handler
from stripe_webhook_handler import stripe_webhook_handler
from tenant_store import DynamoDBTenantStore
from tenant_templates_handler import tenant_templates_handler
from tenant_users_handler import tenant_users_handler
from templates_handler import get_templates_handler
from tenants_handler import create_tenant_handler as self_serve_create_tenant_handler, get_tenants_handler
from upload_handler import upload_url_handler
from users_handler import users_handler
from validate_slug_handler import validate_slug_handler

NOT_FOUND = {"error": "Not found"}


def _with_cors(resp: dict) -> dict:
    """Merge CORS headers into the response and serialize non-string bodies (Decimal-safe)."""
    return finalize_response(resp)


def _ctx(fn):
    """Adapt a ``handler(ctx)`` to the ``(event, context)`` route signature."""
    return lambda event, context: run_with_context(event, fn)


# ---------------------------------------------------------------------------
# Tenant site sub-router: /api/tenant/sites[/{id}[/{action}|/{content}...]]
# ---------------------------------------------------------------------------

_SITE_ACTIONS = {
    ("POST", "upload-url"): upload_url_handler,
    ("POST", "publish"): publish_handler,
    ("POST", "rollback"): rollback_handler,
    ("GET", "draft-token"): draft_token_handler,
    ("POST", "draft-publish"): draft_publish_handler,
}


def tenant_sites_router(ctx: RequestContext) -> dict:
    parts = [p for p in ctx.path[len("/api/tenant/sites"):].split("/") if p]
    if len(parts) == 2 and (ctx.method, parts[1]) in _SITE_ACTIONS:
        return _SITE_ACTIONS[(ctx.method, parts[1])](ctx)
    if len(parts) >= 2 and parts[1].lower() in CONTENT_ENTITIES:
        return content_handler(ctx)
    return sites_handler(ctx)


# ---------------------------------------------------------------------------
# Superadmin: /api/admin/tenants/{slug}[/resource...]
# ---------------------------------------------------------------------------

_ADMIN_DELEGATES = {
    "sites": tenant_sites_router,
    "domains": domains_handler,
    "users": users_handler,
    "tusers": tenant_users_handler,
    "roles": roles_handler,
}


def _as_tenant_request(ctx: RequestContext, slug: str, resource: str, rest: list[str]) -> dict:
    """Run a tenant handler for ``slug`` as an impersonating superadmin (effective role admin)."""
    ctx.require_superadmin()
    if not DynamoDBTenantStore().get_tenant(slug):
        return respond(404, {"error": f"Tenant not found: {slug}"})
    tenant_path = "/".join(["/api/tenant", resource, *rest])
    tenant_ctx = dataclasses.replace(
        ctx,
        event={**ctx.event, "rawPath": tenant_path, "path": tenant_path},
        tenant_slug=slug,
        effective_role="admin",
        is_impersonating=True,
        tenant_item=None,
    )
    return _ADMIN_DELEGATES[resource](tenant_ctx)


def _route_admin_tenants(event, context, path, method):
    parts = [p for p in path[len("/api/admin/tenants/"):].split("/") if p]
    if not parts:
        return respond(404, NOT_FOUND)
    slug, resource, rest = parts[0].lower(), (parts[1] if len(parts) > 1 else None), parts[2:]

    if resource in _ADMIN_DELEGATES:
        return run_with_context(event, lambda ctx: _as_tenant_request(ctx, slug, resource, rest))
    if resource is None and method == "DELETE":
        return run_with_context(event, lambda ctx: delete_tenant_handler(ctx, slug))
    handler = None
    if resource is None:
        handler = {"GET": get_tenant_by_slug_handler, "PATCH": admin_patch_tenant_handler}.get(method)
    elif resource == "settings" and not rest:
        handler = {"GET": get_tenant_by_slug_handler, "PUT": admin_patch_tenant_handler}.get(method)
    return handler(event, context, slug) if handler else respond(404, NOT_FOUND)


def _route_admin_templates(event, context, path, method):
    """Sub-router for /api/admin/templates/{slug}."""
    slug_part = path[len("/api/admin/templates/"):].strip("/")
    if not slug_part or "/" in slug_part:
        return respond(404, NOT_FOUND)
    handler = {"GET": get_template_handler, "PUT": update_template_handler, "DELETE": delete_template_handler}.get(method)
    if not handler:
        return respond(405, {"error": "Method not allowed."})
    return handler(event, context, slug_part.lower())


# ---------------------------------------------------------------------------
# Route registry
# ---------------------------------------------------------------------------

_EXACT_ROUTES = [
    ("GET", "/api/health", lambda e, c: respond(200, {"status": "ok", "service": "9host-api"})),
    ("POST", "/api/auth/site-login", site_login_handler),
    ("GET", "/api/tenants", get_tenants_handler),
    ("POST", "/api/tenants", self_serve_create_tenant_handler),
    ("GET", "/api/validate-slug", validate_slug_handler),
    ("GET", "/api/tenant", get_tenant_handler),
    ("PUT", "/api/tenant", put_tenant_handler),
    ("PATCH", "/api/tenant", patch_tenant_handler),
    ("GET", "/api/tenant/analytics", get_analytics_handler),
    ("POST", "/api/tenant/billing/checkout", billing_checkout_handler),
    ("POST", "/api/tenant/billing/portal", billing_portal_handler),
    ("GET", "/api/templates", get_templates_handler),
    ("POST", "/api/webhooks/stripe", stripe_webhook_handler),
    ("GET", "/api/admin/users", admin_global_users_handler),
    ("GET", "/api/admin/stats", admin_stats_handler),
    ("GET", "/api/admin/edge-kvs", _ctx(edge_kvs_handler)),
    ("GET", "/api/admin/tenants", list_all_tenants_handler),
    ("POST", "/api/admin/tenants", create_tenant_handler),
    ("GET", "/api/admin/templates", list_templates_handler),
    ("POST", "/api/admin/templates", create_template_handler),
]
_EXACT_LOOKUP = {(m, p): h for m, p, h in _EXACT_ROUTES}

# Ordered — first match wins. handler(event, context, path, method)
_PREFIX_ROUTES = [
    ("/api/tenant/sites", lambda e, c, p, m: run_with_context(e, tenant_sites_router)),
    ("/api/tenant/domains", lambda e, c, p, m: run_with_context(e, domains_handler)),
    ("/api/tenant/users", lambda e, c, p, m: run_with_context(e, users_handler)),
    ("/api/tenant/tusers", lambda e, c, p, m: run_with_context(e, tenant_users_handler)),
    ("/api/tenant/roles", lambda e, c, p, m: run_with_context(e, roles_handler)),
    ("/api/tenant/templates", lambda e, c, p, m: tenant_templates_handler(e, c)),
    ("/api/webhooks/stripe", lambda e, c, p, m: stripe_webhook_handler(e, c)),
    ("/api/admin/tenants/", _route_admin_tenants),
    ("/api/admin/templates/", _route_admin_templates),
]

# Exact-path routes that answer 405 (not 404) for other methods
_METHOD_RESTRICTED = {
    "/api/tenant/billing/checkout": {"POST"},
    "/api/tenant/billing/portal": {"POST"},
}


def lambda_handler(event: dict, context: dict) -> dict:
    """API Gateway HTTP API (v2) proxy entry point, behind the safe error boundary (Bug #8)."""
    try:
        return _with_cors(_lambda_handler_impl(event, context))
    except Exception as e:  # noqa: BLE001 - full traceback to CloudWatch, scrubbed 500 to client
        return internal_error_response(event, e)


def _lambda_handler_impl(event: dict, context: dict) -> dict:
    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    method = (event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod") or "GET").upper()
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}
    handler = _EXACT_LOOKUP.get((method, path))
    if handler:
        return handler(event, context)
    if path in _METHOD_RESTRICTED:
        return respond(405, {"error": "Method not allowed."})
    for prefix, route_fn in _PREFIX_ROUTES:
        if path.startswith(prefix):
            return route_fn(event, context, path, method)
    return respond(404, NOT_FOUND)
