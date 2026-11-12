"""
Templates API — GET /api/templates (Task 1.30).

Returns platform templates filtered by tenant tier (tenant.tier >= template.tier_required).
Requires tenant_slug, Cognito auth, tenant membership.
"""

import json

from dynamodb_helpers import get_tenant_item, query_templates, query_tenant_templates
from request_context import RequestContext
from tenant_store import DynamoDBTenantStore
from tier_config import tier_rank as _tier_rank


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def get_templates_handler(ctx: RequestContext) -> dict:
    """
    GET /api/templates — list templates available to tenant (tier-filtered).
    """
    tenant_slug, _ = ctx.require_tenant_member()
    table = DynamoDBTenantStore().table

    # Get tenant tier
    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    tenant_item = resp.get("Item")
    if not tenant_item:
        return _json_response(404, {"error": "Tenant not found."})
    tenant_tier_rank = _tier_rank(tenant_item.get("tier", "FREE"))

    # Query platform templates
    resp = table.query(**query_templates())
    templates = []
    for item in resp.get("Items", []):
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
                "is_custom": False,
            })

    # Query tenant templates (Task 1.124)
    tenant_resp = table.query(**query_tenant_templates(tenant_slug))
    for item in tenant_resp.get("Items", []):
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
                "forked_from": item.get("forked_from"),
                "is_custom": True,
            })

    templates.sort(key=lambda t: (not t.get("is_custom"), t["slug"]))
    return _json_response(200, {"templates": templates})
