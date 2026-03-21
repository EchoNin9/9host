"""
9host API Lambda handler — main entry point for API Gateway.

Dispatches requests to route handlers via declarative route registry.
Uses tenant middleware (X-Tenant-Slug, subdomain, or path param) for
tenant-scoped operations.
"""

import json

from admin_users_handler import (
    admin_stats_handler,
    admin_users_handler as admin_global_users_handler,
)
from admin_handler import (
    create_tenant_handler,
    get_tenant_by_slug_handler,
    list_all_tenants_handler,
    patch_tenant_handler as admin_patch_tenant_handler,
)
from admin_tenant_resources import (
    admin_domains_handler,
    admin_roles_handler,
    admin_sites_handler,
    admin_users_handler,
    delete_tenant_handler,
    put_tenant_settings_handler,
)
from admin_templates_handler import (
    create_template_handler,
    delete_template_handler,
    get_template_handler,
    list_templates_handler,
    update_template_handler,
)
from analytics_handler import get_analytics_handler
from domains_handler import domains_handler
from handler_example import get_tenant_handler, patch_tenant_handler, put_tenant_handler
from sites_handler import sites_handler
from roles_handler import roles_handler
from tenant_users_handler import tenant_users_handler
from users_handler import users_handler
from billing_handler import billing_checkout_handler, billing_portal_handler
from site_auth_handler import site_login_handler
from stripe_webhook_handler import stripe_webhook_handler
from tenants_handler import create_tenant_handler as self_serve_create_tenant_handler, get_tenants_handler
from templates_handler import get_templates_handler
from tenant_templates_handler import tenant_templates_handler
from validate_slug_handler import validate_slug_handler
from upload_handler import upload_url_handler
from content_handler import content_handler
from publish_handler import draft_publish_handler, publish_handler
from draft_handler import draft_token_handler
from rollback_handler import rollback_handler
from default_site_handler import default_site_handler


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "300",
}


def _with_cors(resp: dict) -> dict:
    """Merge CORS headers into the response so cross-origin fetches succeed."""
    h = resp.get("headers") or {}
    resp["headers"] = {**CORS_HEADERS, **h}
    return resp


def _json_response(status: int, body: dict, headers: dict | None = None) -> dict:
    h = {"Content-Type": "application/json", **CORS_HEADERS}
    if headers:
        h.update(headers)
    return {
        "statusCode": status,
        "headers": h,
        "body": json.dumps(body),
    }


def _error_500(message: str = "Internal server error", detail: dict | None = None) -> dict:
    """Return 500 with CORS headers (Task 1.52: prevent 502 on unhandled exceptions)."""
    body = {"error": message}
    if detail:
        body["detail"] = detail
    return {
        "statusCode": 500,
        "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps(body),
    }


# ---------------------------------------------------------------------------
# Route registry (Task 1.143)
#
# Each entry is (method, path, handler) where:
#   method  — HTTP verb ("GET", "POST", …) or "*" for any method
#   path    — exact path (matched after stripping trailing slash)
#   handler — callable(event, context) returning a response dict
#
# For prefix routes that delegate to sub-routers, use _PREFIX_ROUTES below.
# ---------------------------------------------------------------------------

_EXACT_ROUTES: list[tuple[str, str, callable]] = [
    # Health
    ("GET", "/api/health", lambda e, c: _json_response(200, {"status": "ok", "service": "9host-api"})),
    # Auth
    ("POST", "/api/auth/site-login", site_login_handler),
    # Tenants (self-serve)
    ("GET", "/api/tenants", get_tenants_handler),
    ("POST", "/api/tenants", self_serve_create_tenant_handler),
    # Validation
    ("GET", "/api/validate-slug", validate_slug_handler),
    # Tenant metadata
    ("GET", "/api/tenant/default-site", default_site_handler),
    ("GET", "/api/tenant", get_tenant_handler),
    ("PUT", "/api/tenant", put_tenant_handler),
    ("PATCH", "/api/tenant", patch_tenant_handler),
    # Tenant analytics
    ("GET", "/api/tenant/analytics", get_analytics_handler),
    # Billing
    ("POST", "/api/tenant/billing/checkout", billing_checkout_handler),
    ("POST", "/api/tenant/billing/portal", billing_portal_handler),
    # Templates (public)
    ("GET", "/api/templates", get_templates_handler),
    # Stripe webhook
    ("POST", "/api/webhooks/stripe", stripe_webhook_handler),
    # Superadmin
    ("GET", "/api/admin/users", admin_global_users_handler),
    ("GET", "/api/admin/stats", admin_stats_handler),
    ("GET", "/api/admin/tenants", list_all_tenants_handler),
    ("POST", "/api/admin/tenants", create_tenant_handler),
    ("GET", "/api/admin/templates", list_templates_handler),
    ("POST", "/api/admin/templates", create_template_handler),
]

# Build a lookup dict: {(method, path): handler} for O(1) matching
_EXACT_LOOKUP: dict[tuple[str, str], callable] = {(m, p): h for m, p, h in _EXACT_ROUTES}


# ---------------------------------------------------------------------------
# Prefix routes — checked in order, first match wins.
# (prefix, handler_func)  where handler_func(event, context, path, method)
# ---------------------------------------------------------------------------

def _route_tenant_sites(event, context, path, method):
    """Sub-router for /api/tenant/sites/..."""
    if "/upload-url" in path and path.endswith("/upload-url") and method == "POST":
        return upload_url_handler(event, context)
    if "/publish" in path and path.endswith("/publish") and method == "POST":
        return publish_handler(event, context)
    if "/rollback" in path and path.endswith("/rollback") and method == "POST":
        return rollback_handler(event, context)
    if "/draft-token" in path and path.endswith("/draft-token") and method == "GET":
        return draft_token_handler(event, context)
    if "/draft-publish" in path and path.endswith("/draft-publish") and method == "POST":
        return draft_publish_handler(event, context)
    if "/pages" in path or "/posts" in path or "/events" in path or "/media" in path:
        return content_handler(event, context)
    return sites_handler(event, context)


def _route_admin_tenants(event, context, path, method):
    """Sub-router for /api/admin/tenants/{slug}[/resource]."""
    suffix = path[len("/api/admin/tenants/"):].strip("/")
    parts = suffix.split("/") if suffix else []
    slug_lower = (parts[0] or "").lower() if parts else ""
    if not slug_lower:
        return _json_response(404, {"error": "Not found"})

    if len(parts) == 1:
        if method == "GET":
            return get_tenant_by_slug_handler(event, context, slug_lower)
        if method == "PATCH":
            return admin_patch_tenant_handler(event, context, slug_lower)
        if method == "DELETE":
            return delete_tenant_handler(event, context, slug_lower)
    elif parts[1] == "domains":
        return admin_domains_handler(event, context, slug_lower, "/".join(parts[1:]))
    elif parts[1] == "sites":
        return admin_sites_handler(event, context, slug_lower, "/".join(parts[1:]))
    elif parts[1] == "users":
        return admin_users_handler(event, context, slug_lower, "/".join(parts[1:]))
    elif parts[1] == "roles" and len(parts) == 2 and method == "GET":
        return admin_roles_handler(event, context, slug_lower)
    elif parts[1] == "settings" and len(parts) == 2:
        if method == "GET":
            return get_tenant_by_slug_handler(event, context, slug_lower)
        if method == "PUT":
            return put_tenant_settings_handler(event, context, slug_lower)
    elif len(parts) >= 2:
        return _json_response(404, {"error": "Not found"})

    return _json_response(404, {"error": "Not found"})


def _route_admin_templates(event, context, path, method):
    """Sub-router for /api/admin/templates/{slug}."""
    slug_part = path[len("/api/admin/templates/"):].strip("/")
    if not slug_part or "/" in slug_part:
        return _json_response(404, {"error": "Not found"})
    slug_lower = slug_part.lower()
    if method == "GET":
        return get_template_handler(event, context, slug_lower)
    if method == "PUT":
        return update_template_handler(event, context, slug_lower)
    if method == "DELETE":
        return delete_template_handler(event, context, slug_lower)
    return _json_response(405, {"error": "Method not allowed."})


# Ordered list — first match wins
_PREFIX_ROUTES: list[tuple[str, callable]] = [
    ("/api/tenant/sites", _route_tenant_sites),
    ("/api/tenant/domains", lambda e, c, p, m: domains_handler(e, c)),
    ("/api/tenant/users", lambda e, c, p, m: users_handler(e, c)),
    ("/api/tenant/tusers", lambda e, c, p, m: tenant_users_handler(e, c)),
    ("/api/tenant/roles", lambda e, c, p, m: roles_handler(e, c)),
    ("/api/tenant/templates", lambda e, c, p, m: tenant_templates_handler(e, c)),
    ("/api/webhooks/stripe", lambda e, c, p, m: stripe_webhook_handler(e, c)),
    ("/api/admin/tenants/", _route_admin_tenants),
    ("/api/admin/templates/", _route_admin_templates),
]

# Methods that return 405 for non-matching methods on exact-path routes
_METHOD_RESTRICTED: dict[str, set[str]] = {
    "/api/tenant/billing/checkout": {"POST"},
    "/api/tenant/billing/portal": {"POST"},
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context: dict) -> dict:
    """API Gateway HTTP API (v2) proxy integration entry point."""
    try:
        return _lambda_handler_impl(event, context)
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        print(f"[9host] 500: {type(e).__name__}: {e}\n{tb}")  # CloudWatch
        detail = {
            "type": type(e).__name__,
            "message": str(e),
            "traceback": tb,
        }
        return _error_500(str(e), detail=detail)


def _lambda_handler_impl(event: dict, context: dict) -> dict:
    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    method = (event.get("requestContext", {}).get("http", {}).get("method") or
              event.get("httpMethod") or "GET")

    # CORS preflight
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    # 1. Exact route lookup — O(1)
    handler = _EXACT_LOOKUP.get((method, path))
    if handler:
        return _with_cors(handler(event, context))

    # 2. Check if path matches an exact route but wrong method → 405
    if path in _METHOD_RESTRICTED and method not in _METHOD_RESTRICTED[path]:
        return _json_response(405, {"error": "Method not allowed."})

    # 3. Prefix routes — checked in order
    for prefix, route_fn in _PREFIX_ROUTES:
        if path.startswith(prefix):
            return _with_cors(route_fn(event, context, path, method))

    # 4. Fallback
    return _with_cors(get_tenant_handler(event, context))
