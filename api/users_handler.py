"""
Tenant users API — GET /api/tenant/users, GET/PUT /api/tenant/users/{sub}/permissions (Tasks 1.27, 1.25).

List tenant users (admin/manager only). Get/update per-user module permissions (admin/manager only).
"""

import json
import os
from urllib.parse import unquote

import boto3

from auth_helpers import get_sub_from_access_token, require_tenant_admin_or_manager
from dynamodb_helpers import (
    get_user_permissions_item,
    get_user_profile_item,
    pk_tenant,
    query_tenants_for_user,
    query_users_in_tenant,
    sk_user_permissions,
)
from middleware import with_tenant

# Module keys for permissions (tenantadmin configures what tenantuser can access)
MODULE_KEYS = ("sites", "domains", "analytics", "settings")


def _json_response(status: int, body: dict, empty_body: bool = False) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": "" if empty_body else json.dumps(body),
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


def _extract_sub_from_path(path: str) -> str | None:
    """Extract sub from /api/tenant/users/{sub} or /api/tenant/users/{sub}/permissions."""
    prefix = "/api/tenant/users/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :].strip("/")
    if not rest:
        return None
    parts = rest.split("/")
    if parts[0]:
        return unquote(parts[0])
    return None


def _is_permissions_path(path: str) -> bool:
    """Check if path is /api/tenant/users/{sub}/permissions."""
    prefix = "/api/tenant/users/"
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix) :].strip("/")
    parts = rest.split("/")
    return len(parts) >= 2 and parts[1] == "permissions"


def _profile_to_response(item: dict) -> dict:
    """Convert profile item to API response."""
    sk = item.get("sk", "")
    sub = ""
    if sk.startswith("USER#") and sk.endswith("#PROFILE"):
        sub = sk.replace("USER#", "").replace("#PROFILE", "")
    return {
        "sub": sub or item.get("sub", ""),
        "email": item.get("email", ""),
        "name": item.get("name", ""),
        "role": item.get("role", "member"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def _list_users(table, tenant_slug: str) -> dict:
    """List users in tenant (profiles only)."""
    params = query_users_in_tenant(tenant_slug)
    resp = table.query(**params)
    users = []
    for item in resp.get("Items", []):
        sk = item.get("sk", "")
        if sk.endswith("#PROFILE"):
            users.append(_profile_to_response(item))
    return _json_response(200, {"users": users})


def _get_permissions(table, tenant_slug: str, target_sub: str) -> dict:
    """Get permissions for user in tenant."""
    key = get_user_permissions_item(tenant_slug, target_sub)
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        # Default: all modules allowed (role-based access applies)
        return _json_response(200, {"permissions": {k: True for k in MODULE_KEYS}})
    perms = item.get("permissions", {})
    if isinstance(perms, dict):
        result = {k: perms.get(k, True) for k in MODULE_KEYS}
    else:
        result = {k: True for k in MODULE_KEYS}
    return _json_response(200, {"permissions": result})


def _put_permissions(table, tenant_slug: str, target_sub: str, body: dict) -> dict:
    """Update permissions for user in tenant."""
    from datetime import datetime, timezone

    perms = body.get("permissions", {})
    if not isinstance(perms, dict):
        return _json_response(400, {"error": "permissions must be an object."})
    # Merge with defaults: only update keys present in request
    existing = table.get_item(Key=get_user_permissions_item(tenant_slug, target_sub))
    current = (existing.get("Item") or {}).get("permissions", {})
    if isinstance(current, dict):
        merged = {k: current.get(k, True) for k in MODULE_KEYS}
    else:
        merged = {k: True for k in MODULE_KEYS}
    for k in MODULE_KEYS:
        if k in perms:
            merged[k] = bool(perms[k])
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_user_permissions(target_sub),
        "permissions": merged,
        "updated_at": now,
    }
    table.put_item(Item=item)
    return _json_response(200, {"permissions": merged})


@with_tenant
def users_handler(event: dict, context: dict) -> dict:
    """
    GET /api/tenant/users — list tenant users (admin/manager).
    GET /api/tenant/users/{sub}/permissions — get permissions (admin/manager).
    PUT /api/tenant/users/{sub}/permissions — update permissions (admin/manager).
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

    # All operations require admin/manager
    ok, err = require_tenant_admin_or_manager(table, sub, tenant_slug)
    if not ok:
        return _json_response(403, {"error": err or "Forbidden."})

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    )

    target_sub = _extract_sub_from_path(path)
    is_permissions = _is_permissions_path(path)

    if not is_permissions and not target_sub:
        # GET /api/tenant/users — list users
        if method == "GET":
            return _list_users(table, tenant_slug)
        return _json_response(405, {"error": "Method not allowed."})

    if is_permissions and target_sub:
        # Verify target user is in tenant (has profile)
        profile_resp = table.get_item(Key=get_user_profile_item(tenant_slug, target_sub))
        if not profile_resp.get("Item"):
            return _json_response(404, {"error": "User not found in tenant."})
        if method == "GET":
            return _get_permissions(table, tenant_slug, target_sub)
        if method == "PUT":
            body = _parse_body(event) or {}
            return _put_permissions(table, tenant_slug, target_sub, body)
        return _json_response(405, {"error": "Method not allowed."})

    return _json_response(404, {"error": "Not found."})
