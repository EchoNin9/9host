"""
GET /api/tenants — list tenants for authenticated user (GSI byUser).

Requires Cognito access token in Authorization: Bearer <token>.
"""

import json
import os

import boto3

from auth_helpers import get_sub_from_access_token
from dynamodb_helpers import pk_tenant, query_tenants_for_user, sk_tenant


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def get_tenants_handler(event: dict, context: dict) -> dict:
    """
    GET /api/tenants — returns tenants for the authenticated user.
    Requires Authorization: Bearer <cognito_access_token>.
    """
    region = os.environ.get("AWS_REGION", "us-east-1")
    sub = get_sub_from_access_token(event, region=region)
    if not sub:
        return _json_response(401, {"error": "Unauthorized. Provide Authorization: Bearer <access_token>."})

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Query GSI byUser for user's tenant memberships
    params = query_tenants_for_user(sub)
    resp = table.query(**params)
    items = resp.get("Items", [])

    # Extract tenant slugs from gsi1sk (TENANT#{slug}#PROFILE)
    slugs = set()
    role_by_slug = {}
    for item in items:
        gsi1sk = item.get("gsi1sk", "")
        if gsi1sk.startswith("TENANT#") and "#PROFILE" in gsi1sk:
            slug = gsi1sk.replace("TENANT#", "").replace("#PROFILE", "")
            slugs.add(slug)
            role_by_slug[slug] = item.get("role", "member")

    # BatchGet tenant metadata for name
    tenants = []
    if slugs:
        keys = [{"pk": pk_tenant(s), "sk": sk_tenant()} for s in slugs]
        batch = table.meta.client.batch_get_item(
            RequestItems={
                table_name: {"Keys": keys},
            }
        )
        tenant_rows = batch.get("Responses", {}).get(table_name, [])
        by_slug = {r["pk"].replace("TENANT#", ""): r for r in tenant_rows}

        for slug in sorted(slugs):
            row = by_slug.get(slug, {})
            tenants.append({
                "slug": slug,
                "name": row.get("name", slug),
                "role": role_by_slug.get(slug, "member"),
            })

    return _json_response(200, {"tenants": tenants})
