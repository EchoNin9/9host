"""
9host API Lambda handler — main entry point for API Gateway.

Dispatches requests to route handlers. Uses tenant middleware (X-Tenant-Slug,
subdomain, or path param) for tenant-scoped operations.
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
from tenants_handler import get_tenants_handler
from templates_handler import get_templates_handler


# CORS headers for Lambda proxy — API Gateway cors_configuration may not apply to $default
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


def lambda_handler(event: dict, context: dict) -> dict:
    """
    API Gateway HTTP API (v2) proxy integration entry point.

    Routes:
      GET /api/tenant, /api/tenant/ — tenant metadata (requires tenant_slug)
      GET /api/tenant/analytics — analytics placeholder (Pro+ tier)
      GET/POST/PUT/DELETE /api/tenant/sites — sites CRUD
      GET/POST/DELETE /api/tenant/domains — custom domains (Pro+ tier)
      GET /api/admin/tenants — list all tenants (superadmin)
      GET /api/admin/tenants/{slug} — get any tenant (superadmin)
      $default — fallback to tenant handler for now
    """
    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    method = (event.get("requestContext", {}).get("http", {}).get("method") or
              event.get("httpMethod") or "GET")

    # CORS preflight — must return 200 for browser to allow actual request
    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": "",
        }

    if method == "GET" and path in ("/api/health", "/api/health/"):
        return _json_response(200, {"status": "ok", "service": "9host-api"})

    if method == "POST" and path in ("/api/auth/site-login", "/api/auth/site-login/"):
        return _with_cors(site_login_handler(event, context))

    if method == "GET" and path in ("/api/tenants", "/api/tenants/"):
        return _with_cors(get_tenants_handler(event, context))

    if path in ("/api/tenant", "/api/tenant/"):
        if method == "GET":
            return _with_cors(get_tenant_handler(event, context))
        if method == "PUT":
            return _with_cors(put_tenant_handler(event, context))
        if method == "PATCH":
            return _with_cors(patch_tenant_handler(event, context))

    if method == "GET" and path in ("/api/tenant/analytics", "/api/tenant/analytics/"):
        return _with_cors(get_analytics_handler(event, context))

    if path.startswith("/api/tenant/sites"):
        return _with_cors(sites_handler(event, context))

    if path.startswith("/api/tenant/domains"):
        return _with_cors(domains_handler(event, context))

    if path.startswith("/api/tenant/users"):
        return _with_cors(users_handler(event, context))

    if path.startswith("/api/tenant/tusers"):
        return _with_cors(tenant_users_handler(event, context))

    if path.startswith("/api/tenant/roles"):
        return _with_cors(roles_handler(event, context))

    if path == "/api/tenant/billing/checkout":
        if method == "POST":
            return _with_cors(billing_checkout_handler(event, context))
        return _json_response(405, {"error": "Method not allowed."})
    if path == "/api/tenant/billing/portal":
        if method == "POST":
            return _with_cors(billing_portal_handler(event, context))
        return _json_response(405, {"error": "Method not allowed."})

    if method == "GET" and path in ("/api/templates", "/api/templates/"):
        return _with_cors(get_templates_handler(event, context))

    # Stripe webhook (Task 1.19) — no tenant, no Cognito auth
    if path.startswith("/api/webhooks/stripe"):
        return _with_cors(stripe_webhook_handler(event, context))

    # Superadmin routes (Task 1.22, 1.29, 1.34, 1.48)
    if method == "GET" and path in ("/api/admin/users", "/api/admin/users/"):
        return _with_cors(admin_global_users_handler(event, context))
    if method == "GET" and path in ("/api/admin/stats", "/api/admin/stats/"):
        return _with_cors(admin_stats_handler(event, context))
    if method == "GET" and path in ("/api/admin/tenants", "/api/admin/tenants/"):
        return _with_cors(list_all_tenants_handler(event, context))
    if method == "POST" and path in ("/api/admin/tenants", "/api/admin/tenants/"):
        return _with_cors(create_tenant_handler(event, context))
    if path.startswith("/api/admin/tenants/"):
        suffix = path[len("/api/admin/tenants/"):].strip("/")
        parts = suffix.split("/") if suffix else []
        slug_lower = (parts[0] or "").lower()
        if not slug_lower:
            pass  # fall through
        elif len(parts) == 1:
            if method == "GET":
                return _with_cors(get_tenant_by_slug_handler(event, context, slug_lower))
            if method == "PATCH":
                return _with_cors(admin_patch_tenant_handler(event, context, slug_lower))
            if method == "DELETE":
                return _with_cors(delete_tenant_handler(event, context, slug_lower))
        elif parts[1] == "domains":
            return _with_cors(admin_domains_handler(event, context, slug_lower, "/".join(parts[1:])))
        elif parts[1] == "sites":
            return _with_cors(admin_sites_handler(event, context, slug_lower, "/".join(parts[1:])))
        elif parts[1] == "users":
            return _with_cors(admin_users_handler(event, context, slug_lower, "/".join(parts[1:])))
        elif parts[1] == "settings" and len(parts) == 2:
            if method == "PUT":
                return _with_cors(put_tenant_settings_handler(event, context, slug_lower))
        elif len(parts) >= 2:
            return _json_response(404, {"error": "Not found"})

    # Superadmin templates (Task 1.31)
    if method == "GET" and path in ("/api/admin/templates", "/api/admin/templates/"):
        return _with_cors(list_templates_handler(event, context))
    if method == "POST" and path in ("/api/admin/templates", "/api/admin/templates/"):
        return _with_cors(create_template_handler(event, context))
    if path.startswith("/api/admin/templates/"):
        slug_part = path[len("/api/admin/templates/"):].strip("/")
        if slug_part and "/" not in slug_part:
            slug_lower = slug_part.lower()
            if method == "GET":
                return _with_cors(get_template_handler(event, context, slug_lower))
            if method == "PUT":
                return _with_cors(update_template_handler(event, context, slug_lower))
            if method == "DELETE":
                return _with_cors(delete_template_handler(event, context, slug_lower))

    return _with_cors(get_tenant_handler(event, context))
