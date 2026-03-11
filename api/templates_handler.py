"""
Templates API — GET /api/templates (Task 1.30).

Returns platform templates filtered by tenant tier (tenant.tier >= template.tier_required).
Requires tenant_slug, Cognito auth, tenant membership.
"""

import json
import os

import boto3

from auth_helpers import get_sub_from_access_token
from dynamodb_helpers import get_tenant_item, query_tenants_for_user, query_templates
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


def _user_is_tenant_member(table, sub: str, tenant_slug: str) -> bool:
    """Check if user is a member of the tenant via GSI byUser."""
    params = query_tenants_for_user(sub)
    resp = table.query(**params)
    for item in resp.get("Items", []):
        gsi1sk = item.get("gsi1sk", "")
        if f"TENANT#{tenant_slug}#PROFILE" == gsi1sk:
            return True
    return False


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

    region = os.environ.get("AWS_REGION", "us-east-1")
    sub = get_sub_from_access_token(event, region=region)
    if not sub:
        return _json_response(
            401,
            {"error": "Unauthorized. Provide Authorization: Bearer <access_token>."},
        )

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    if not _user_is_tenant_member(table, sub, tenant_slug):
        return _json_response(403, {"error": "Forbidden. Not a member of this tenant."})

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
