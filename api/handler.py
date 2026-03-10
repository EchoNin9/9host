"""
9host API Lambda handler — main entry point for API Gateway.

Dispatches requests to route handlers. Uses tenant middleware (X-Tenant-Slug,
subdomain, or path param) for tenant-scoped operations.
"""

import json

from admin_handler import get_tenant_by_slug_handler, list_all_tenants_handler
from analytics_handler import get_analytics_handler
from domains_handler import domains_handler
from handler_example import get_tenant_handler
from sites_handler import sites_handler
from stripe_webhook_handler import stripe_webhook_handler
from tenants_handler import get_tenants_handler


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
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

    if method == "GET" and path in ("/api/health", "/api/health/"):
        return _json_response(200, {"status": "ok", "service": "9host-api"})

    if method == "GET" and path in ("/api/tenants", "/api/tenants/"):
        return get_tenants_handler(event, context)

    if method == "GET" and path in ("/api/tenant", "/api/tenant/"):
        return get_tenant_handler(event, context)

    if method == "GET" and path in ("/api/tenant/analytics", "/api/tenant/analytics/"):
        return get_analytics_handler(event, context)

    if path.startswith("/api/tenant/sites"):
        return sites_handler(event, context)

    if path.startswith("/api/tenant/domains"):
        return domains_handler(event, context)

    # Stripe webhook (Task 1.19) — no tenant, no Cognito auth
    if path.startswith("/api/webhooks/stripe"):
        return stripe_webhook_handler(event, context)

    # Superadmin routes (Task 1.22)
    if method == "GET" and path in ("/api/admin/tenants", "/api/admin/tenants/"):
        return list_all_tenants_handler(event, context)
    if method == "GET" and path.startswith("/api/admin/tenants/"):
        slug_part = path[len("/api/admin/tenants/"):].strip("/")
        if slug_part and "/" not in slug_part:
            return get_tenant_by_slug_handler(event, context, slug_part.lower())

    return get_tenant_handler(event, context)
