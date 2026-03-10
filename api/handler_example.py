"""
Tenant metadata handler — GET /api/tenant (Task 1.26: owner_sub).

Fetches tenant from DynamoDB. Returns name, tier, owner_sub, etc.
"""

import json
import os

import boto3

from auth_helpers import get_sub_from_access_token
from dynamodb_helpers import get_tenant_item, query_tenants_for_user
from middleware import extract_tenant_slug, with_tenant


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


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
def get_tenant_handler(event: dict, context: dict) -> dict:
    """
    GET /api/tenant — tenant metadata. Requires tenant_slug, Cognito auth, tenant membership.
    Returns name, tier, owner_sub (Task 1.26), etc.
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(
            400,
            {"error": "Missing tenant. Use subdomain (acme.echo9.net) or X-Tenant-Slug header."},
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

    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Tenant not found."})

    return _json_response(
        200,
        {
            "tenant_slug": tenant_slug,
            "name": item.get("name", tenant_slug),
            "tier": item.get("tier", "FREE"),
            "owner_sub": item.get("owner_sub"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        },
    )


def raw_handler(event: dict, context: dict) -> dict:
    """
    Example without decorator: manually extract tenant_slug.
    """
    tenant_slug = extract_tenant_slug(event)
    event["tenant_slug"] = tenant_slug
    # ... rest of handler
    return {"statusCode": 200, "body": json.dumps({"tenant_slug": tenant_slug})}
