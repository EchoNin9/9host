"""
Superadmin API — GET /api/admin/tenants, GET /api/admin/tenants/{slug} (Task 1.22),
PATCH /api/admin/tenants/{slug} (Task 1.29).

Requires Cognito auth and superadmin group membership.
"""

import json
import os

import boto3

from auth_helpers import get_sub_from_access_token, is_superadmin
from dynamodb_helpers import get_tenant_item


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _require_superadmin(event: dict) -> tuple[str | None, dict | None]:
    """
    Require authenticated superadmin. Returns (sub, None) if ok, (None, error_response) if not.
    """
    region = os.environ.get("AWS_REGION", "us-east-1")
    user_pool_id = os.environ.get("USER_POOL_ID", "")

    sub = get_sub_from_access_token(event, region=region)
    if not sub:
        return None, _json_response(
            401,
            {"error": "Unauthorized. Provide Authorization: Bearer <access_token>."},
        )

    if not is_superadmin(sub, user_pool_id, region=region):
        return None, _json_response(
            403,
            {"error": "Forbidden. Superadmin access required."},
        )

    return sub, None


def list_all_tenants_handler(event: dict, context: dict) -> dict:
    """
    GET /api/admin/tenants — list all tenants (superadmin only).
    """
    _, err = _require_superadmin(event)
    if err:
        return err

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Scan for tenant items (pk begins_with TENANT#, sk = TENANT)
    resp = table.scan(
        FilterExpression="begins_with(pk, :prefix) AND sk = :sk",
        ExpressionAttributeValues={":prefix": "TENANT#", ":sk": "TENANT"},
    )
    items = resp.get("Items", [])

    tenants = []
    for item in items:
        slug = item.get("pk", "").replace("TENANT#", "")
        if slug:
            tenants.append({
                "slug": slug,
                "name": item.get("name", slug),
                "tier": item.get("tier", "FREE"),
                "owner_sub": item.get("owner_sub"),
            })

    # Sort by slug
    tenants.sort(key=lambda t: t["slug"])

    return _json_response(200, {"tenants": tenants})


def _parse_body(event: dict) -> dict | None:
    """Parse JSON body from event."""
    body = event.get("body")
    if not body:
        return None
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None
    return body


def get_tenant_by_slug_handler(event: dict, context: dict, tenant_slug: str) -> dict:
    """
    GET /api/admin/tenants/{slug} — get any tenant by slug (superadmin only).
    """
    _, err = _require_superadmin(event)
    if err:
        return err

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    item = resp.get("Item")

    if not item:
        return _json_response(404, {"error": f"Tenant not found: {tenant_slug}"})

    return _json_response(
        200,
        {
            "slug": tenant_slug,
            "name": item.get("name", tenant_slug),
            "tier": item.get("tier", "FREE"),
            "owner_sub": item.get("owner_sub"),
            "module_overrides": item.get("module_overrides") or {},
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        },
    )


def patch_tenant_handler(event: dict, context: dict, tenant_slug: str) -> dict:
    """
    PATCH /api/admin/tenants/{slug} — update tier, name, module_overrides (superadmin only).
    Body: { "tier"?: "FREE"|"PRO"|"BUSINESS", "name"?: string, "module_overrides"?: map }.
    """
    _, err = _require_superadmin(event)
    if err:
        return err

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": f"Tenant not found: {tenant_slug}"})

    body = _parse_body(event) or {}
    updates = []
    expr_vals = {}
    expr_names = {}

    if "tier" in body:
        tier = (body.get("tier") or "FREE").upper()
        if tier not in ("FREE", "PRO", "BUSINESS"):
            return _json_response(400, {"error": "tier must be FREE, PRO, or BUSINESS"})
        updates.append("tier = :tier")
        expr_vals[":tier"] = tier

    if "name" in body:
        name = (body.get("name") or "").strip()
        updates.append("name = :name")
        expr_vals[":name"] = name if name else tenant_slug

    if "module_overrides" in body:
        mo = body.get("module_overrides")
        if not isinstance(mo, dict):
            return _json_response(400, {"error": "module_overrides must be a map"})
        # Validate keys: only known feature keys
        valid_keys = {"custom_domains", "advanced_analytics"}
        clean_mo = {k: bool(v) for k, v in mo.items() if k in valid_keys}
        updates.append("module_overrides = :mo")
        expr_vals[":mo"] = clean_mo

    if not updates:
        return _json_response(400, {"error": "Provide at least one of: tier, name, module_overrides"})

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    updates.append("updated_at = :u")
    expr_vals[":u"] = now

    update_expr = "SET " + ", ".join(updates)
    table.update_item(
        Key=get_tenant_item(tenant_slug),
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expr_vals,
        ExpressionAttributeNames=expr_names or None,
    )

    # Fetch updated item
    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    updated = resp.get("Item", {})
    return _json_response(
        200,
        {
            "slug": tenant_slug,
            "name": updated.get("name", tenant_slug),
            "tier": updated.get("tier", "FREE"),
            "owner_sub": updated.get("owner_sub"),
            "module_overrides": updated.get("module_overrides") or {},
            "updated_at": updated.get("updated_at"),
        },
    )
