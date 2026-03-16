"""
GET /api/tenants — list tenants for authenticated user (GSI byUser).
POST /api/tenants — self-serve tenant creation (Task 4.1).

Requires Cognito access token in Authorization: Bearer <token>.
"""

import json
import os
import re
from datetime import datetime, timezone

import boto3

from auth_helpers import get_sub_from_access_token
from dynamodb_helpers import (
    get_tenant_item,
    gsi1pk_user,
    gsi1sk_tenant_profile,
    gsi3pk_entity_user,
    gsi3sk_user,
    pk_tenant,
    query_by_site_slug,
    query_tenants_for_user,
    sk_tenant,
    sk_user_profile,
)


# Slug: lowercase alphanumeric + hyphen, max 60 chars
TENANT_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


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


def _get_user_email_name(event: dict, region: str) -> tuple[str, str]:
    """Fetch email and name from Cognito GetUser. Returns (email, name)."""
    auth = (event.get("headers") or {}).get("authorization") or (event.get("headers") or {}).get("Authorization") or ""
    if not auth.startswith("Bearer "):
        return "", ""
    token = auth[7:].strip()
    if not token:
        return "", ""
    try:
        client = boto3.client("cognito-idp", region_name=region)
        resp = client.get_user(AccessToken=token)
        email, name = "", ""
        for attr in resp.get("UserAttributes", []):
            if attr.get("Name") == "email":
                email = attr.get("Value", "")
            elif attr.get("Name") in ("name", "preferred_username"):
                if not name:
                    name = attr.get("Value", "")
        return email, name
    except Exception:
        return "", ""


def create_tenant_handler(event: dict, context: dict) -> dict:
    """
    POST /api/tenants — self-serve tenant creation (Task 4.1).
    Any authenticated Cognito user can create a tenant. Tier is always FREE.
    Body: { "slug": string (max 60), "name"?: string }.
    """
    region = os.environ.get("AWS_REGION", "us-east-1")
    sub = get_sub_from_access_token(event, region=region)
    if not sub:
        return _json_response(
            401,
            {"error": "Unauthorized. Provide Authorization: Bearer <access_token>."},
        )

    body = _parse_body(event) or {}
    slug = (body.get("slug") or "").strip().lower().replace(" ", "-")
    name = (body.get("name") or "").strip()

    if not slug:
        return _json_response(400, {"error": "slug is required"})
    if len(slug) > 60:
        return _json_response(400, {"error": "slug must be at most 60 characters"})
    if not TENANT_SLUG_PATTERN.match(slug):
        return _json_response(
            400,
            {"error": "slug must be lowercase alphanumeric and hyphen (e.g. acme-corp, my-band)"},
        )

    if not name:
        name = slug.replace("-", " ").title()

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Validate slug uniqueness: tenant and site slugs share global namespace (Task 1.76)
    resp = table.get_item(Key=get_tenant_item(slug))
    if resp.get("Item"):
        return _json_response(409, {"error": f"Tenant already exists: {slug}"})

    # Reserve tenant slugs from site slugs: reject if slug is taken by a site
    slug_resp = table.query(**query_by_site_slug(slug))
    if slug_resp.get("Items"):
        return _json_response(409, {"error": f"Slug '{slug}' is already in use by a site."})

    now = datetime.now(timezone.utc).isoformat()
    email, user_name = _get_user_email_name(event, region)

    # Create tenant (Task 1.88: storage_used_bytes default 0). Self-serve: tier = FREE only.
    tenant_item = {
        "pk": pk_tenant(slug),
        "sk": sk_tenant(),
        "name": name,
        "tier": "FREE",
        "owner_sub": sub,
        "storage_used_bytes": 0,
        "created_at": now,
        "updated_at": now,
    }
    table.put_item(Item=tenant_item)

    # Create user profile (creator as admin) and membership
    profile_item = {
        "pk": pk_tenant(slug),
        "sk": sk_user_profile(sub),
        "gsi1pk": gsi1pk_user(sub),
        "gsi1sk": gsi1sk_tenant_profile(slug),
        "gsi3pk": gsi3pk_entity_user(),
        "gsi3sk": gsi3sk_user(slug, sub),
        "sub": sub,
        "email": email,
        "name": user_name or name,
        "role": "admin",
        "created_at": now,
        "updated_at": now,
    }
    table.put_item(Item=profile_item)

    return _json_response(
        201,
        {
            "slug": slug,
            "name": name,
            "tier": "FREE",
            "owner_sub": sub,
            "created_at": now,
            "updated_at": now,
        },
    )
