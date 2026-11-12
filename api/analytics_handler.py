"""
GET /api/tenant/analytics — placeholder analytics for Pro+ tier (2.8).

Requires: tenant membership and the advanced_analytics feature (Pro+ tier unless
module_overrides turns it on/off).
Returns: placeholder metrics for charts (page views, visitors, top pages).
"""

import json
from datetime import datetime, timedelta

from request_context import HttpError, RequestContext


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


def get_analytics_handler(ctx: RequestContext) -> dict:
    """
    GET /api/tenant/analytics — returns placeholder analytics for Pro+ tenants.
    Requires tenant membership and the advanced_analytics feature (tier + module_overrides).
    """
    tenant_slug, _ = ctx.require_permission("analytics", ("admin", "manager", "editor", "member"))
    try:
        ctx.require_feature("advanced_analytics")
    except HttpError:
        tier = ((ctx.tenant_item or {}).get("tier") or "FREE").upper()
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
