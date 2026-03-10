"""
Superadmin API — GET /api/admin/tenants, GET /api/admin/tenants/{slug} (Task 1.22).

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
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        },
    )
