"""
Tenant users API — non-Cognito user CRUD (Task 1.46).

GET /api/tenant/tusers — list non-Cognito users in tenant
POST /api/tenant/tusers — create user: { username, password, display_name, role }
PUT /api/tenant/tusers/{username} — edit role, display_name, password
DELETE /api/tenant/tusers/{username} — delete user

Requires tenant admin or manager (Cognito or non-Cognito).
"""

import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import unquote

import bcrypt
import boto3

from auth_helpers import require_tenant_auth, require_tenant_admin_or_manager, role_is_admin_or_manager
from dynamodb_helpers import (
    get_role_item,
    get_tuser_item,
    gsi3pk_entity_user,
    gsi3sk_tuser,
    pk_tenant,
    query_tusers_in_tenant,
    sk_tuser,
)
from middleware import with_tenant

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$")


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


def _tuser_to_response(item: dict) -> dict:
    sk = item.get("sk", "")
    username = sk.replace("TUSER#", "") if sk.startswith("TUSER#") else ""
    return {
        "username": username or item.get("username", ""),
        "display_name": item.get("display_name", ""),
        "role": item.get("role", "member"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def _extract_username_from_path(path: str) -> str | None:
    """Extract username from /api/tenant/tusers/{username}."""
    prefix = "/api/tenant/tusers/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :].strip("/")
    if not rest or "/" in rest:
        return None
    return unquote(rest)


@with_tenant
def tenant_users_handler(event: dict, context: dict) -> dict:
    """
    GET/POST/PUT/DELETE /api/tenant/tusers — non-Cognito tenant user CRUD.
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

    username = _extract_username_from_path(path)
    base_path = "/api/tenant/tusers"
    is_list_or_create = path in (base_path, f"{base_path}/")

    if method == "GET" and is_list_or_create:
        params = query_tusers_in_tenant(tenant_slug)
        resp = table.query(**params)
        users = [_tuser_to_response(item) for item in resp.get("Items", [])]
        return _json_response(200, {"users": users})

    if method == "POST" and is_list_or_create:
        body = _parse_body(event) or {}
        username_val = (body.get("username") or "").strip()
        password = body.get("password") or ""
        display_name = (body.get("display_name") or "").strip()
        role_val = (body.get("role") or "member").lower()

        if not username_val:
            return _json_response(400, {"error": "username is required."})
        if not password or len(password) < 8:
            return _json_response(400, {"error": "password is required and must be at least 8 characters."})
        if not USERNAME_PATTERN.match(username_val):
            return _json_response(400, {"error": "username must be alphanumeric, dots, underscores, hyphens."})
        if role_val not in ("manager", "member"):
            role_key = get_role_item(tenant_slug, role_val)
            if not table.get_item(Key=role_key).get("Item"):
                return _json_response(400, {"error": f"role must be manager, member, or an existing custom role."})

        key = get_tuser_item(tenant_slug, username_val)
        if table.get_item(Key=key).get("Item"):
            return _json_response(409, {"error": f"User {username_val} already exists in this tenant."})

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        now = datetime.now(timezone.utc).isoformat()

        item = {
            "pk": pk_tenant(tenant_slug),
            "sk": sk_tuser(username_val),
            "username": username_val,
            "password_hash": password_hash,
            "display_name": display_name,
            "role": role_val,
            "created_at": now,
            "updated_at": now,
            "gsi3pk": gsi3pk_entity_user(),
            "gsi3sk": gsi3sk_tuser(tenant_slug, username_val),
        }
        table.put_item(Item=item)
        return _json_response(201, {"user": _tuser_to_response(item)})

    if method == "PUT" and username:
        key = get_tuser_item(tenant_slug, username)
        item = table.get_item(Key=key).get("Item")
        if not item:
            return _json_response(404, {"error": "User not found."})

        body = _parse_body(event) or {}
        if "role" in body:
            r = (body.get("role") or "").lower()
            if r in ("manager", "member"):
                item["role"] = r
            else:
                role_key = get_role_item(tenant_slug, r)
                if table.get_item(Key=role_key).get("Item"):
                    item["role"] = r
                else:
                    return _json_response(400, {"error": "role must be manager, member, or an existing custom role."})
        if "display_name" in body:
            item["display_name"] = str(body["display_name"]).strip()
        if "password" in body and body["password"]:
            pw = body["password"]
            if len(pw) < 8:
                return _json_response(400, {"error": "password must be at least 8 characters."})
            item["password_hash"] = bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        table.put_item(Item=item)
        return _json_response(200, {"user": _tuser_to_response(item)})

    if method == "DELETE" and username:
        key = get_tuser_item(tenant_slug, username)
        if not table.get_item(Key=key).get("Item"):
            return _json_response(404, {"error": "User not found."})
        table.delete_item(Key=key)
        return _json_response(204, {}, empty_body=True)

    return _json_response(405, {"error": "Method not allowed."})
