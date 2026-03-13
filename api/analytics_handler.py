"""
GET /api/tenant/analytics — placeholder analytics for Pro+ tier (2.8).

Requires: tenant_slug (header/subdomain), Cognito auth, tenant membership, tier >= Pro.
Returns: placeholder metrics for charts (page views, visitors, top pages).
"""

import json
import os
from datetime import datetime, timedelta

import boto3

from auth_helpers import require_tenant_auth
from dynamodb_helpers import get_tenant_item
from middleware import extract_tenant_slug, with_tenant
from tier_config import tiers_with_pro_features

# Tiers that have advanced_analytics (Pro+), includes VIP (Task 1.82)
ANALYTICS_TIERS = tiers_with_pro_features()


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _generate_placeholder_analytics(tenant_slug: str) -> dict:
    """Generate placeholder analytics data for charts/metrics UI."""
    today = datetime.utcnow().date()
    page_views = []
    for i in range(30, 0, -1):
        d = today - timedelta(days=i)
        # Deterministic-ish placeholder: slight variation per day
        count = 50 + (hash(f"{tenant_slug}{d}") % 150)
        page_views.append({"date": d.isoformat(), "count": count})

    return {
        "period": "last_30_days",
        "page_views_over_time": page_views,
        "total_page_views": sum(p["count"] for p in page_views),
        "unique_visitors": 420,
        "top_pages": [
            {"path": "/", "views": 1250},
            {"path": "/about", "views": 340},
            {"path": "/contact", "views": 180},
        ],
        "placeholder": True,
    }


@with_tenant
def get_analytics_handler(event: dict, context: dict) -> dict:
    """
    GET /api/tenant/analytics — returns placeholder analytics for Pro+ tenants.
    Requires tenant_slug (X-Tenant-Slug or subdomain), Cognito auth, tenant membership.
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(
            400,
            {"error": "Missing tenant. Use subdomain or X-Tenant-Slug header."},
        )

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    region = os.environ.get("AWS_REGION", "us-east-1")
    auth_result = require_tenant_auth(event, table, tenant_slug, region)
    if auth_result[0] is not True:
        _, err_resp = auth_result
        return _json_response(err_resp.get("statusCode", 401), json.loads(err_resp.get("body", "{}")))

    # Get tenant to check tier
    tenant_resp = table.get_item(Key=get_tenant_item(tenant_slug))
    tenant = tenant_resp.get("Item")
    tier = (tenant or {}).get("tier", "FREE").upper()

    if tier not in ANALYTICS_TIERS:
        return _json_response(
            403,
            {
                "error": "Advanced Analytics requires Pro, Business, or VIP tier.",
                "tier": tier,
                "upgrade_required": True,
            },
        )

    analytics = _generate_placeholder_analytics(tenant_slug)
    return _json_response(200, analytics)
