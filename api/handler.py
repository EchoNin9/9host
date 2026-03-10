"""
9host API Lambda handler — main entry point for API Gateway.

Dispatches requests to route handlers. Uses tenant middleware (X-Tenant-Slug,
subdomain, or path param) for tenant-scoped operations.
"""

import json

from analytics_handler import get_analytics_handler
from handler_example import get_tenant_handler
from sites_handler import sites_handler
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

    return get_tenant_handler(event, context)
