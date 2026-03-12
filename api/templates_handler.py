"""
Templates API — GET /api/templates (Task 1.30).

Returns platform templates filtered by tenant tier (tenant.tier >= template.tier_required).
Requires tenant_slug, Cognito auth, tenant membership.
"""

import json
import os

import boto3

from auth_helpers import require_tenant_auth
from dynamodb_helpers import get_tenant_item, query_templates
from middleware import with_tenant


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _tier_rank(tier: str) -> int:
    """Tier rank for comparison. FREE=0, PRO=1, BUSINESS=2."""
    t = (tier or "FREE").upper()
    if t == "FREE":
        return 0
    if t == "PRO":
        return 1
    if t == "BUSINESS":
        return 2
    return 0


@with_tenant
def get_templates_handler(event: dict, context: dict) -> dict:
    """
    GET /api/templates — list templates available to tenant (tier-filtered).
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

    # Get tenant tier
    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    tenant_item = resp.get("Item")
    if not tenant_item:
        return _json_response(404, {"error": "Tenant not found."})
    tenant_tier_rank = _tier_rank(tenant_item.get("tier", "FREE"))

    # Query all platform templates
    resp = table.query(**query_templates())
    items = resp.get("Items", [])

    templates = []
    for item in items:
        sk = item.get("sk", "")
        if not sk.startswith("TEMPLATE#"):
            continue
        slug = sk.replace("TEMPLATE#", "")
        tier_required = item.get("tier_required", "FREE")
        if _tier_rank(tier_required) <= tenant_tier_rank:
            templates.append({
                "slug": slug,
                "name": item.get("name", slug),
                "description": item.get("description", ""),
                "tier_required": tier_required,
                "components": item.get("components") or {},
            })

    templates.sort(key=lambda t: t["slug"])
    return _json_response(200, {"templates": templates})
