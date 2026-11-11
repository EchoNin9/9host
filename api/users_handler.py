"""
Tenant users API (Tasks 1.25, 1.27, 1.39) — also serves /api/admin/tenants/{slug}/users.

GET  /api/tenant/users                     list Cognito members (admin/manager)
GET  /api/tenant/users/{id}/permissions    module permissions of a member or TUSER (admin/manager)
PUT  /api/tenant/users/{id}/permissions    update module permissions (admin/manager)
POST /api/tenant/users                     add Cognito member {sub|email, role, name?} or
                                           TUSER {type: "tuser", username, password, ...} (superadmin)
PUT  /api/tenant/users/{id}                update role/name/email of a member or TUSER (superadmin)
DELETE /api/tenant/users/{id}              remove a member (+permissions) or TUSER (superadmin)
"""

import os
from datetime import datetime, timezone
from urllib.parse import unquote

import boto3

from request_context import RequestContext, respond
from tenant_store import DynamoDBTenantStore
from tenant_users_handler import create_tuser

BASE_PATH = "/api/tenant/users"
MANAGE_ROLES = ("admin", "manager")
MEMBER_ROLES = ("admin", "manager", "editor", "member")
MODULE_KEYS = ("sites", "domains", "analytics", "settings")


def _member_out(m: dict) -> dict:
    return {
        "sub": m.get("sub", ""),
        "email": m.get("email", ""),
        "name": m.get("name", ""),
        "role": m.get("role", "member"),
        "created_at": m.get("created_at", ""),
        "updated_at": m.get("updated_at", ""),
    }


def _tuser_out(t: dict) -> dict:
    """TUSER in member shape (sub = username) for the unified users list UI."""
    return {**_member_out({**t, "sub": t["username"], "email": "", "name": t.get("display_name") or t["username"]}),
            "type": "tuser"}


def _cognito_lookup(sub_or_email: str) -> dict | None:
    """Cognito user {"sub", "email", "name"} by sub/username or email; None if not found."""
    pool = os.environ.get("USER_POOL_ID", "")
    if not pool or not sub_or_email or '"' in sub_or_email:
        return None
    client = boto3.client("cognito-idp", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    try:
        users = []
        if "@" in sub_or_email:
            users = client.list_users(UserPoolId=pool, Filter=f'email = "{sub_or_email}"', Limit=1).get("Users", [])
        if users:
            username, attrs = users[0].get("Username", ""), users[0].get("Attributes", [])
        else:
            resp = client.admin_get_user(UserPoolId=pool, Username=sub_or_email)
            username, attrs = resp.get("Username", ""), resp.get("UserAttributes", [])
    except Exception:  # noqa: BLE001 - unknown user / Cognito unavailable
        return None
    a = {x.get("Name"): x.get("Value", "") for x in attrs}
    return {
        "sub": a.get("sub") or username,
        "email": a.get("email", ""),
        "name": a.get("name") or a.get("preferred_username") or username,
    }


def _permissions(store, tenant_slug: str, target: str, body: dict | None) -> dict:
    current = store.get_permissions(tenant_slug, target)
    merged = {k: current.get(k, True) for k in MODULE_KEYS}
    if body is None:
        return respond(200, {"permissions": merged})
    perms = body.get("permissions", {})
    if not isinstance(perms, dict):
        return respond(400, {"error": "permissions must be an object."})
    merged.update({k: bool(perms[k]) for k in MODULE_KEYS if k in perms})
    store.put_permissions(tenant_slug, target, merged, datetime.now(timezone.utc).isoformat())
    return respond(200, {"permissions": merged})


def _add_member(store, tenant_slug: str, body: dict) -> dict:
    if (body.get("type") or "cognito").lower() == "tuser":
        status, result = create_tuser(store, tenant_slug, body)
        return respond(status, {"user": _tuser_out(result)} if status == 201 else result)

    sub = (body.get("sub") or "").strip()
    email = (body.get("email") or "").strip()
    name = (body.get("name") or "").strip()
    role = (body.get("role") or "member").lower()
    found = None if (sub and email and name) else _cognito_lookup(sub or email)
    if not sub and email:
        if not found:
            return respond(404, {"error": f"No Cognito user found with email: {email}"})
        sub = found["sub"]
    if not sub:
        return respond(400, {"error": "sub or email is required."})
    if role not in MEMBER_ROLES:
        return respond(400, {"error": "role must be admin, manager, editor, or member."})
    if store.get_member(tenant_slug, sub):
        return respond(409, {"error": "User already in tenant."})
    now = datetime.now(timezone.utc).isoformat()
    member = store.put_member(tenant_slug, {
        "sub": sub,
        "email": email or (found or {}).get("email", ""),
        "name": name or (found or {}).get("name", "") or sub[:8],
        "role": role,
        "created_at": now,
        "updated_at": now,
    })
    return respond(201, {"user": _member_out(member)})


def _update_member(store, tenant_slug: str, target: str, body: dict) -> dict:
    member = store.get_member(tenant_slug, target)
    tuser = None if member else store.get_tuser(tenant_slug, target)
    if not member and not tuser:
        return respond(404, {"error": "User not found in tenant."})
    item = member or tuser
    role = str(body.get("role", "")).lower()
    if role in MEMBER_ROLES:
        item["role"] = role
    if member:
        item.update({k: str(body[k]).strip() for k in ("email", "name") if k in body})
    elif "name" in body:
        item["display_name"] = str(body["name"]).strip()
    item["updated_at"] = datetime.now(timezone.utc).isoformat()
    if member:
        return respond(200, {"user": _member_out(store.put_member(tenant_slug, item))})
    return respond(200, {"user": _tuser_out(store.put_tuser(tenant_slug, item))})


def users_handler(ctx: RequestContext) -> dict:
    tenant_slug, _ = ctx.require_tenant_member(MANAGE_ROLES)
    store = DynamoDBTenantStore()
    method = ctx.method
    parts = [unquote(p) for p in ctx.path[len(BASE_PATH):].split("/") if p]
    target = parts[0] if parts else None

    if not parts:
        if method == "GET":
            return respond(200, {"users": [_member_out(m) for m in store.list_cognito_members(tenant_slug)]})
        if method == "POST":
            ctx.require_superadmin()
            return _add_member(store, tenant_slug, ctx.json_body())
        return respond(405, {"error": "Method not allowed."})

    if len(parts) == 2 and parts[1] == "permissions":
        if not store.get_member(tenant_slug, target) and not store.get_tuser(tenant_slug, target):
            return respond(404, {"error": "User not found in tenant."})
        if method in ("GET", "PUT"):
            return _permissions(store, tenant_slug, target, ctx.json_body() if method == "PUT" else None)
        return respond(405, {"error": "Method not allowed."})

    if len(parts) == 1 and method in ("PUT", "DELETE"):
        ctx.require_superadmin()
        if method == "PUT":
            return _update_member(store, tenant_slug, target, ctx.json_body())
        if store.get_member(tenant_slug, target):
            store.delete_member(tenant_slug, target)
        elif store.get_tuser(tenant_slug, target):
            store.delete_tuser(tenant_slug, target)
        else:
            return respond(404, {"error": "User not found in tenant."})
        return respond(204)
    return respond(404, {"error": "Not found."})
