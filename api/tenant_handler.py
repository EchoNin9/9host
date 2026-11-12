"""
Tenant metadata handler — GET /api/tenant (Task 1.26: owner_sub, 1.28: module_overrides, resolved_features).

Fetches tenant from DynamoDB. Returns name, tier, owner_sub, module_overrides, resolved_features in GET.
"""

from tier_config import (
    CONTENT_MODULE_KEYS,
    FEATURE_KEYS,
    tier_has_feature as _tier_has_feature,
    tier_has_module as _tier_has_module,
    tier_rank as _tier_rank,
)

import json
import os
import time

import boto3

from dynamodb_helpers import get_tenant_item
from request_context import RequestContext
from tenant_store import DynamoDBTenantStore


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


_OWNER_EMAIL_TTL_SECONDS = 300  # 5 minutes
_clock = time.monotonic  # patchable in tests
_owner_email_cache: dict[str, tuple[float, str]] = {}  # owner sub -> (expires_at, email)


def _owner_email(owner_sub: str, region: str) -> str:
    """Owner email via Cognito admin_get_user, cached per owner sub for 5 minutes."""
    now = _clock()
    hit = _owner_email_cache.get(owner_sub)
    if hit and hit[0] > now:
        return hit[1]
    email = ""
    try:
        client = boto3.client("cognito-idp", region_name=region)
        resp = client.admin_get_user(UserPoolId=os.environ.get("USER_POOL_ID", ""), Username=owner_sub)
        for attr in resp.get("UserAttributes", []):
            if attr.get("Name") == "email":
                email = attr.get("Value", "")
                break
    except Exception:
        return ""  # failures are not cached
    _owner_email_cache[owner_sub] = (now + _OWNER_EMAIL_TTL_SECONDS, email)
    return email


def get_tenant_handler(ctx: RequestContext) -> dict:
    """
    GET /api/tenant — tenant metadata. Requires tenant membership.
    Returns name, tier, owner_sub (Task 1.26), etc.
    """
    tenant_slug, _ = ctx.require_tenant_member()
    table = DynamoDBTenantStore().table
    region = os.environ.get("AWS_REGION", "us-east-1")

    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Tenant not found."})

    tier = (item.get("tier") or "FREE").upper()
    module_overrides = item.get("module_overrides") or {}
    owner_sub = item.get("owner_sub")

    # Resolve owner email from Cognito (Task 1.50)
    owner_email = _owner_email(owner_sub, region) if owner_sub else ""

    # Resolved features: tier base + module_overrides override (Task 1.28, 1.94)
    resolved_features = {}
    clean_module_overrides = {}
    for fk in FEATURE_KEYS:
        if fk in module_overrides:
            val = module_overrides[fk]
            resolved_features[fk] = bool(val)
            clean_module_overrides[fk] = bool(val)
        else:
            resolved_features[fk] = _tier_has_feature(tier, fk)
    for mk in CONTENT_MODULE_KEYS:
        if mk in module_overrides:
            val = module_overrides[mk]
            resolved_features[mk] = bool(val)
            clean_module_overrides[mk] = bool(val)
        else:
            resolved_features[mk] = _tier_has_module(tier, mk)

    body = {
        "tenant_slug": tenant_slug,
        "name": str(item.get("name") or tenant_slug),
        "tier": tier,
        "owner_sub": owner_sub,
        "owner_email": owner_email,
        "module_overrides": clean_module_overrides,
        "resolved_features": resolved_features,
        "storage_used_bytes": int(item.get("storage_used_bytes") or 0),
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


def put_tenant_handler(ctx: RequestContext) -> dict:
    """
    PUT /api/tenant — transfer owner (Task 2.17). Requires current user to be owner.
    Body: { "owner_sub": "<new_owner_sub>" }. Only Cognito users can be owner.
    """
    tenant_slug, _ = ctx.require_tenant_member()
    table = DynamoDBTenantStore().table
    sub = ctx.principal.identifier

    if ctx.principal.kind != "cognito":
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

    body = _parse_body(ctx.event) or {}
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


def patch_tenant_handler(ctx: RequestContext) -> dict:
    """
    PATCH /api/tenant — update module_overrides (Task 2.22). Requires admin/manager.
    Body: { "module_overrides": { "custom_domains": bool, "advanced_analytics": bool } }.
    """
    tenant_slug, _ = ctx.require_tenant_member(("admin", "manager"))
    table = DynamoDBTenantStore().table

    body = _parse_body(ctx.event) or {}
    mo = body.get("module_overrides")
    if not isinstance(mo, dict):
        return _json_response(400, {"error": "module_overrides must be an object"})

    # Fetch tenant to validate tier (Task 1.80: only allow features tenant's tier supports)
    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    tenant_item = resp.get("Item")
    if not tenant_item:
        return _json_response(404, {"error": "Tenant not found."})
    tier = tenant_item.get("tier", "FREE")

    # Reject enabling features/modules the tier doesn't support
    for k, v in mo.items():
        if k in FEATURE_KEYS:
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
        elif k in CONTENT_MODULE_KEYS:
            if v and not _tier_has_module(tier, k):
                return _json_response(
                    403,
                    {
                        "error": f"Cannot enable {k} on {tier} tier. Upgrade required.",
                        "feature": k,
                        "tier": tier,
                        "upgrade_required": True,
                    },
                )

    valid_keys = set(FEATURE_KEYS) | set(CONTENT_MODULE_KEYS)
    clean_mo = {k: bool(v) for k, v in mo.items() if k in valid_keys}

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
    for mk in CONTENT_MODULE_KEYS:
        if mk in module_overrides:
            resolved_features[mk] = bool(module_overrides[mk])
        else:
            resolved_features[mk] = _tier_has_module(tier, mk)
    return _json_response(
        200,
        {
            "tenant_slug": tenant_slug,
            "module_overrides": module_overrides,
            "resolved_features": resolved_features,
        },
    )

