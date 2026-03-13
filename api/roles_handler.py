"""
Custom roles API — tenant-defined roles (Task 1.47).

GET /api/tenant/roles — list custom roles
POST /api/tenant/roles — create: { name, permissions }
PUT /api/tenant/roles/{name} — update permissions
DELETE /api/tenant/roles/{name} — delete (fail if users assigned)

Requires tenant admin (Cognito admin or tenant_user with manager-equivalent).
"""

import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import unquote

import boto3

from auth_helpers import require_tenant_auth, require_tenant_admin_or_manager, role_is_admin_or_manager
from dynamodb_helpers import (
    get_role_item,
    pk_tenant,
    query_roles_in_tenant,
    query_tusers_in_tenant,
    query_users_in_tenant,
    sk_role,
)
from middleware import with_tenant

ROLE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$")
RESERVED_ROLES = ("manager", "member", "admin", "editor")
MODULE_KEYS = ("sites", "domains", "analytics", "settings", "users")


def _json_response(status: int, body: dict, empty_body: bool = False) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": "" if empty_body else json.dumps(body),
    }


def _parse_body(event: dict) -> dict | None:
    body = event.get("body")
    if not body:
        return None
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None
    return body


def _role_to_response(item: dict) -> dict:
    sk = item.get("sk", "")
    name = sk.replace("ROLE#", "") if sk.startswith("ROLE#") else ""
    perms = item.get("permissions", {})
    return {
        "name": name or item.get("name", ""),
        "permissions": {k: bool(perms.get(k, False)) for k in MODULE_KEYS},
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def _extract_role_name_from_path(path: str) -> str | None:
    """Extract role name from /api/tenant/roles/{name}."""
    prefix = "/api/tenant/roles/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :].strip("/")
    if not rest or "/" in rest:
        return None
    return unquote(rest)


def _any_user_has_role(table, tenant_slug: str, role_name: str) -> bool:
    """Check if any Cognito or TUSER has this role."""
    # Cognito users
    params = query_users_in_tenant(tenant_slug)
    resp = table.query(**params)
    for item in resp.get("Items", []):
        if item.get("sk", "").endswith("#PROFILE") and item.get("role") == role_name:
            return True
    # TUSER
    params = query_tusers_in_tenant(tenant_slug)
    resp = table.query(**params)
    for item in resp.get("Items", []):
        if item.get("role") == role_name:
            return True
    return False


@with_tenant
def roles_handler(event: dict, context: dict) -> dict:
    """
    GET/POST/PUT/DELETE /api/tenant/roles — custom role CRUD.
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

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    )

    role_name = _extract_role_name_from_path(path)
    base_path = "/api/tenant/roles"
    is_list_or_create = path in (base_path, f"{base_path}/")

    if method == "GET" and is_list_or_create:
        params = query_roles_in_tenant(tenant_slug)
        resp = table.query(**params)
        roles = [_role_to_response(item) for item in resp.get("Items", [])]
        return _json_response(200, {"roles": roles})

    if method == "POST" and is_list_or_create:
        body = _parse_body(event) or {}
        name = (body.get("name") or "").strip().lower()
        permissions = body.get("permissions")
        if not isinstance(permissions, dict):
            permissions = {}

        if not name:
            return _json_response(400, {"error": "name is required."})
        if not ROLE_NAME_PATTERN.match(name):
            return _json_response(400, {"error": "name must be alphanumeric, underscores, hyphens."})
        if name in RESERVED_ROLES:
            return _json_response(400, {"error": f"Role name '{name}' is reserved."})

        key = get_role_item(tenant_slug, name)
        if table.get_item(Key=key).get("Item"):
            return _json_response(409, {"error": f"Role {name} already exists."})

        perms_clean = {k: bool(permissions.get(k, False)) for k in MODULE_KEYS}
        now = datetime.now(timezone.utc).isoformat()

        item = {
            "pk": pk_tenant(tenant_slug),
            "sk": sk_role(name),
            "name": name,
            "permissions": perms_clean,
            "created_at": now,
            "updated_at": now,
        }
        table.put_item(Item=item)
        return _json_response(201, {"role": _role_to_response(item)})

    if method == "PUT" and role_name:
        key = get_role_item(tenant_slug, role_name)
        item = table.get_item(Key=key).get("Item")
        if not item:
            return _json_response(404, {"error": "Role not found."})

        body = _parse_body(event) or {}
        permissions = body.get("permissions")
        if isinstance(permissions, dict):
            perms_clean = {k: bool(permissions.get(k, False)) for k in MODULE_KEYS}
            item["permissions"] = perms_clean

        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        table.put_item(Item=item)
        return _json_response(200, {"role": _role_to_response(item)})

    if method == "DELETE" and role_name:
        key = get_role_item(tenant_slug, role_name)
        if not table.get_item(Key=key).get("Item"):
            return _json_response(404, {"error": "Role not found."})

        if _any_user_has_role(table, tenant_slug, role_name):
            return _json_response(
                400,
                {"error": "Cannot delete role: users are assigned to it. Reassign users first."},
            )

        table.delete_item(Key=key)
        return _json_response(204, {}, empty_body=True)

    return _json_response(405, {"error": "Method not allowed."})
