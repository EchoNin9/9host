"""
Tenant metadata handler — GET /api/tenant (Task 1.26: owner_sub, 1.28: module_overrides, resolved_features).

Fetches tenant from DynamoDB. Returns name, tier, owner_sub, module_overrides, resolved_features in GET.
"""

from tier_config import FEATURE_KEYS, tier_has_feature as _tier_has_feature, tier_rank as _tier_rank

import json
import os

import boto3

from auth_helpers import require_tenant_auth, require_tenant_admin_or_manager, role_is_admin_or_manager
from dynamodb_helpers import get_tenant_item, query_tenants_for_user
from middleware import extract_tenant_slug, with_tenant


def _json_response(status: int, body: dict) -> dict:
    """Return JSON response. Handles DynamoDB Decimal for JSON serialization."""
    from decimal import Decimal

    def _default(obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=_default),
    }


def _user_is_tenant_member(table, sub: str, tenant_slug: str) -> bool:
    """Check if Cognito user is a member of the tenant via GSI byUser."""
    from dynamodb_helpers import query_tenants_for_user

    params = query_tenants_for_user(sub)
    resp = table.query(**params)
    for item in resp.get("Items", []):
        if item.get("gsi1sk") == f"TENANT#{tenant_slug}#PROFILE":
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

    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Tenant not found."})

    tier = (item.get("tier") or "FREE").upper()
    module_overrides = item.get("module_overrides") or {}
    owner_sub = item.get("owner_sub")

    # Resolve owner email from Cognito (Task 1.50)
    owner_email = ""
    if owner_sub:
        try:
            import boto3
            client = boto3.client("cognito-idp", region_name=region)
            resp = client.admin_get_user(
                UserPoolId=os.environ.get("USER_POOL_ID", ""),
                Username=owner_sub,
            )
            for attr in resp.get("UserAttributes", []):
                if attr.get("Name") == "email":
                    owner_email = attr.get("Value", "")
                    break
        except Exception:
            pass

    # Resolved features: tier base + module_overrides override (Task 1.28)
    resolved_features = {}
    clean_module_overrides = {}
    for fk in FEATURE_KEYS:
        if fk in module_overrides:
            val = module_overrides[fk]
            resolved_features[fk] = bool(val)
            clean_module_overrides[fk] = bool(val)
        else:
            resolved_features[fk] = _tier_has_feature(tier, fk)

    body = {
        "tenant_slug": tenant_slug,
        "name": str(item.get("name") or tenant_slug),
        "tier": tier,
        "owner_sub": owner_sub,
        "owner_email": owner_email,
        "module_overrides": clean_module_overrides,
        "resolved_features": resolved_features,
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }
    return _json_response(200, body)


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


@with_tenant
def put_tenant_handler(event: dict, context: dict) -> dict:
    """
    PUT /api/tenant — transfer owner (Task 2.17). Requires current user to be owner.
    Body: { "owner_sub": "<new_owner_sub>" }. Only Cognito users can be owner.
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
    _, sub_or_username, role, is_cognito = auth_result
    sub = sub_or_username if is_cognito else None

    if not is_cognito:
        return _json_response(
            403,
            {"error": "Only Cognito account owners can transfer ownership."},
        )

    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Tenant not found."})

    owner_sub = item.get("owner_sub")
    if owner_sub != sub:
        return _json_response(
            403,
            {"error": "Forbidden. Only the current owner can transfer ownership."},
        )

    body = _parse_body(event) or {}
    new_owner = (body.get("owner_sub") or "").strip()
    if not new_owner:
        return _json_response(400, {"error": "owner_sub is required."})

    if not _user_is_tenant_member(table, new_owner, tenant_slug):
        return _json_response(
            400,
            {"error": "New owner must be a member of this tenant."},
        )

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key=get_tenant_item(tenant_slug),
        UpdateExpression="SET owner_sub = :o, updated_at = :u",
        ExpressionAttributeValues={":o": new_owner, ":u": now},
    )
    return _json_response(
        200,
        {
            "tenant_slug": tenant_slug,
            "owner_sub": new_owner,
        },
    )


@with_tenant
def patch_tenant_handler(event: dict, context: dict) -> dict:
    """
    PATCH /api/tenant — update module_overrides (Task 2.22). Requires admin/manager.
    Body: { "module_overrides": { "custom_domains": bool, "advanced_analytics": bool } }.
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
    _, sub_or_username, role, is_cognito = auth_result
    sub = sub_or_username if is_cognito else None

    if is_cognito:
        ok, err = require_tenant_admin_or_manager(table, sub, tenant_slug)
        if not ok:
            return _json_response(403, {"error": err or "Forbidden."})
    elif not role_is_admin_or_manager(role):
        return _json_response(403, {"error": "Admin or manager role required."})

    body = _parse_body(event) or {}
    mo = body.get("module_overrides")
    if not isinstance(mo, dict):
        return _json_response(400, {"error": "module_overrides must be an object"})

    # Fetch tenant to validate tier (Task 1.80: only allow features tenant's tier supports)
    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    tenant_item = resp.get("Item")
    if not tenant_item:
        return _json_response(404, {"error": "Tenant not found."})
    tier = tenant_item.get("tier", "FREE")

    # Reject enabling features the tier doesn't support
    for k, v in mo.items():
        if k not in FEATURE_KEYS:
            continue
        if v and not _tier_has_feature(tier, k):
            return _json_response(
                403,
                {
                    "error": f"Cannot enable {k} on {tier} tier. Upgrade to Pro or Business.",
                    "feature": k,
                    "tier": tier,
                    "upgrade_required": True,
                },
            )

    clean_mo = {k: bool(v) for k, v in mo.items() if k in FEATURE_KEYS}

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key=get_tenant_item(tenant_slug),
        UpdateExpression="SET module_overrides = :mo, updated_at = :u",
        ExpressionAttributeValues={":mo": clean_mo, ":u": now},
    )
    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    item = resp.get("Item", {})
    tier = item.get("tier", "FREE")
    module_overrides = item.get("module_overrides") or {}
    resolved_features = {}
    for fk in FEATURE_KEYS:
        if fk in module_overrides:
            resolved_features[fk] = bool(module_overrides[fk])
        else:
            resolved_features[fk] = _tier_has_feature(tier, fk)
    return _json_response(
        200,
        {
            "tenant_slug": tenant_slug,
            "module_overrides": module_overrides,
            "resolved_features": resolved_features,
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
