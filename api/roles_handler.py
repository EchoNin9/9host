"""
Custom roles API — tenant-defined roles (Task 1.47). Admin/manager only.
Also serves GET /api/admin/tenants/{slug}/roles.

GET    /api/tenant/roles          list
POST   /api/tenant/roles          create { name, permissions }
PUT    /api/tenant/roles/{name}   update permissions
DELETE /api/tenant/roles/{name}   delete (400 while users are assigned)
"""

import re
from datetime import datetime, timezone
from urllib.parse import unquote

from request_context import RequestContext, respond
from tenant_store import DynamoDBTenantStore

ROLE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$")
RESERVED_ROLES = ("manager", "member", "admin", "editor")
MODULE_KEYS = ("sites", "domains", "analytics", "settings", "users")
BASE_PATH = "/api/tenant/roles"
MANAGE_ROLES = ("admin", "manager")


def _clean_perms(perms) -> dict:
    perms = perms if isinstance(perms, dict) else {}
    return {k: bool(perms.get(k, False)) for k in MODULE_KEYS}


def _role_out(role: dict) -> dict:
    return {
        "name": role.get("name", ""),
        "permissions": _clean_perms(role.get("permissions")),
        "created_at": role.get("created_at", ""),
        "updated_at": role.get("updated_at", ""),
    }


def _role_in_use(store, tenant_slug: str, name: str) -> bool:
    users = store.list_cognito_members(tenant_slug) + store.list_tusers(tenant_slug)
    return any(u.get("role") == name for u in users)


def roles_handler(ctx: RequestContext) -> dict:
    tenant_slug, _ = ctx.require_tenant_member(MANAGE_ROLES)
    store = DynamoDBTenantStore()
    method = ctx.method
    parts = [p for p in ctx.path[len(BASE_PATH):].split("/") if p]
    now = datetime.now(timezone.utc).isoformat()

    if not parts and method == "GET":
        return respond(200, {"roles": [_role_out(r) for r in store.list_roles(tenant_slug)]})
    if not parts and method == "POST":
        body = ctx.json_body()
        name = (body.get("name") or "").strip().lower()
        if not name:
            return respond(400, {"error": "name is required."})
        if not ROLE_NAME_PATTERN.match(name):
            return respond(400, {"error": "name must be alphanumeric, underscores, hyphens."})
        if name in RESERVED_ROLES:
            return respond(400, {"error": f"Role name '{name}' is reserved."})
        if store.get_role(tenant_slug, name):
            return respond(409, {"error": f"Role {name} already exists."})
        role = {"name": name, "permissions": _clean_perms(body.get("permissions")), "created_at": now, "updated_at": now}
        return respond(201, {"role": _role_out(store.put_role(tenant_slug, role))})
    if len(parts) != 1 or method not in ("PUT", "DELETE"):
        return respond(405, {"error": "Method not allowed."})

    name = unquote(parts[0])
    role = store.get_role(tenant_slug, name)
    if not role:
        return respond(404, {"error": "Role not found."})
    if method == "PUT":
        perms = ctx.json_body().get("permissions")
        if isinstance(perms, dict):
            role["permissions"] = _clean_perms(perms)
        role["updated_at"] = now
        return respond(200, {"role": _role_out(store.put_role(tenant_slug, role))})
    if _role_in_use(store, tenant_slug, name):
        return respond(400, {"error": "Cannot delete role: users are assigned to it. Reassign users first."})
    store.delete_role(tenant_slug, name)
    return respond(204)
