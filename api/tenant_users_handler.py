"""
Tenant users API — non-Cognito TenantUser (TUSER) CRUD (Task 1.46). Admin/manager only.

GET    /api/tenant/tusers              list
POST   /api/tenant/tusers              create { username, password, display_name, role }
PUT    /api/tenant/tusers/{username}   edit role, display_name, password
DELETE /api/tenant/tusers/{username}   delete
"""

import re
from datetime import datetime, timezone
from urllib.parse import unquote

import bcrypt

from request_context import RequestContext, respond
from tenant_store import DynamoDBTenantStore

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$")
BASE_PATH = "/api/tenant/tusers"
MANAGE_ROLES = ("admin", "manager")
ROLE_ERROR = "role must be manager, member, or an existing custom role."


def _tuser_out(t: dict) -> dict:
    return {
        "username": t.get("username", ""),
        "display_name": t.get("display_name", ""),
        "role": t.get("role", "member"),
        "created_at": t.get("created_at", ""),
        "updated_at": t.get("updated_at", ""),
    }


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _valid_role(store, tenant_slug: str, role: str) -> bool:
    return role in ("manager", "member") or store.get_role(tenant_slug, role) is not None


def create_tuser(store, tenant_slug: str, body: dict) -> tuple[int, dict]:
    """Validate + create a TUSER. Returns (201, tuser) or (status, {"error": ...})."""
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    role = (body.get("role") or "member").lower()
    if not username:
        return 400, {"error": "username is required."}
    if len(password) < 8:
        return 400, {"error": "password is required and must be at least 8 characters."}
    if not USERNAME_PATTERN.match(username):
        return 400, {"error": "username must be alphanumeric, dots, underscores, hyphens."}
    if not _valid_role(store, tenant_slug, role):
        return 400, {"error": ROLE_ERROR}
    if store.get_tuser(tenant_slug, username):
        return 409, {"error": f"User {username} already exists in this tenant."}
    now = datetime.now(timezone.utc).isoformat()
    tuser = store.put_tuser(tenant_slug, {
        "username": username,
        "password_hash": _hash(password),
        "display_name": (body.get("display_name") or "").strip(),
        "role": role,
        "created_at": now,
        "updated_at": now,
    })
    return 201, tuser


def tenant_users_handler(ctx: RequestContext) -> dict:
    tenant_slug, _ = ctx.require_tenant_member(MANAGE_ROLES)
    store = DynamoDBTenantStore()
    method = ctx.method
    parts = [p for p in ctx.path[len(BASE_PATH):].split("/") if p]

    if not parts and method == "GET":
        return respond(200, {"users": [_tuser_out(t) for t in store.list_tusers(tenant_slug)]})
    if not parts and method == "POST":
        status, result = create_tuser(store, tenant_slug, ctx.json_body())
        return respond(status, {"user": _tuser_out(result)} if status == 201 else result)
    if len(parts) != 1 or method not in ("PUT", "DELETE"):
        return respond(405, {"error": "Method not allowed."})

    username = unquote(parts[0])
    tuser = store.get_tuser(tenant_slug, username)
    if not tuser:
        return respond(404, {"error": "User not found."})
    if method == "DELETE":
        store.delete_tuser(tenant_slug, username)
        return respond(204)

    body = ctx.json_body()
    if "role" in body:
        role = (body.get("role") or "").lower()
        if not _valid_role(store, tenant_slug, role):
            return respond(400, {"error": ROLE_ERROR})
        tuser["role"] = role
    if "display_name" in body:
        tuser["display_name"] = str(body["display_name"]).strip()
    if body.get("password"):
        if len(body["password"]) < 8:
            return respond(400, {"error": "password must be at least 8 characters."})
        tuser["password_hash"] = _hash(body["password"])
    tuser["updated_at"] = datetime.now(timezone.utc).isoformat()
    return respond(200, {"user": _tuser_out(store.put_tuser(tenant_slug, tuser))})
