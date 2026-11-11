"""
Auth helpers for 9host API.

Supports dual-mode auth: Cognito (local JWKS verification) and custom JWT (tenant_user).
Legacy shim over ``request_context`` for handlers not yet on RequestContext
(billing, analytics, templates, tenant metadata, validate-slug).
"""

import os


def _get_header(event: dict, name: str) -> str:
    """Extract header value (case-insensitive)."""
    headers = event.get("headers") or {}
    key_lower = name.lower()
    if isinstance(headers, dict):
        for k, v in headers.items():
            if (k or "").lower() == key_lower:
                return (v or "").strip()
        return ""
    for h in headers:
        k = (h.get("key") or h.get("Key") or "").lower()
        if k == key_lower:
            return (h.get("value") or h.get("Value") or "").strip()
    return ""


def _get_auth_header(event: dict) -> str:
    """Extract Authorization header value."""
    headers = event.get("headers") or {}
    if isinstance(headers, dict):
        return headers.get("authorization") or headers.get("Authorization") or ""
    for h in headers:
        k = (h.get("key") or h.get("Key") or "").lower()
        if k == "authorization":
            return h.get("value") or h.get("Value") or ""
    return ""


def _get_jwt_secret() -> str | None:
    """JWT signing key from Secrets Manager (5-minute module cache, Bug #7)."""
    import secrets_cache

    return secrets_cache.get_secret_string(os.environ.get("JWT_SECRET_ARN"))


def get_auth_context(event: dict, region: str = "us-east-1") -> dict | None:
    """
    Extract auth identity from Bearer token. Dual-mode: Cognito or custom JWT.

    Cognito tokens are verified locally against the cached user-pool JWKS
    (see ``request_context.authenticate``) instead of calling GetUser per request.

    Returns:
      - Cognito: {"user_type": "cognito", "sub": str}
      - Tenant user: {"user_type": "tenant_user", "username": str, "tenant_slug": str, "role": str}
      - None if missing/invalid
    """
    from request_context import authenticate

    principal = authenticate(event, region)
    if principal is None:
        return None
    if principal.kind == "tuser":
        return {
            "user_type": "tenant_user",
            "username": principal.identifier,
            "tenant_slug": principal.token_tenant_slug or "",
            "role": principal.token_role or "member",
        }
    return {
        "user_type": "cognito",
        "sub": principal.identifier,
        "is_superadmin": principal.is_superadmin,
    }


def get_sub_from_access_token(event: dict, region: str = "us-east-1") -> str | None:
    """
    Extract Cognito sub from Bearer token (local JWKS verification).
    Returns sub or None if missing/invalid. Does not support tenant_user JWT.
    """
    ctx = get_auth_context(event, region)
    if ctx and ctx.get("user_type") == "cognito":
        return ctx.get("sub")
    return None


def _member_role(table, sub: str, tenant_slug: str) -> str | None:
    from tenant_store import DynamoDBTenantStore

    return DynamoDBTenantStore(table).get_member_role(tenant_slug, sub)


def require_tenant_auth(
    event: dict,
    table,
    tenant_slug: str,
    region: str = "us-east-1",
) -> tuple[bool, str | None, str | None, bool] | tuple[None, dict]:
    """
    Require tenant auth (Cognito or tenant_user JWT). Returns:
      - (True, sub_or_username, role, is_cognito) if authenticated
      - (None, error_response) if not
    """
    ctx = get_auth_context(event, region)
    if not ctx:
        return None, {
            "statusCode": 401,
            "body": '{"error": "Unauthorized. Provide Authorization: Bearer <access_token>."}',
        }

    if ctx.get("user_type") == "tenant_user":
        if ctx.get("tenant_slug") != tenant_slug:
            return None, {
                "statusCode": 403,
                "body": '{"error": "Forbidden. Tenant user is locked to their tenant."}',
            }
        role = (ctx.get("role") or "member").lower()
        return True, ctx.get("username", ""), role, False

    # Cognito
    sub = ctx.get("sub")
    if not sub:
        return None, {
            "statusCode": 401,
            "body": '{"error": "Unauthorized. Provide Authorization: Bearer <access_token>."}',
        }
    # Superadmin impersonation (Bug #5): X-Impersonate-Tenant or /api/admin/tenants/{slug}/*
    # grants effective "admin" without membership.
    from request_context import impersonated_tenant_slug

    if ctx.get("is_superadmin") and impersonated_tenant_slug(event) == tenant_slug:
        return True, sub, "admin", True
    role = _member_role(table, sub, tenant_slug)
    if role is not None:
        return True, sub, role, True

    return None, {
        "statusCode": 403,
        "body": '{"error": "Forbidden. Not a member of this tenant."}',
    }


def require_tenant_admin_or_manager(
    table, sub: str, tenant_slug: str, event: dict | None = None
) -> tuple[bool, str | None]:
    """
    Require admin or manager role for tenant. Returns (True, None) if ok,
    (False, error_message) if not. When event has X-Impersonate-Tenant and user is superadmin, allows.
    """
    if event:
        impersonate = _get_header(event, "x-impersonate-tenant")
        if impersonate and impersonate.strip().lower() == tenant_slug:
            if is_superadmin(sub, os.environ.get("USER_POOL_ID", ""), os.environ.get("AWS_REGION", "us-east-1")):
                return True, None
    role = _member_role(table, sub, tenant_slug)
    if role is None:
        return False, "Not a member of this tenant."
    if role in ("admin", "manager"):
        return True, None
    return False, "Admin or manager role required for this action."


def role_is_admin_or_manager(role: str) -> bool:
    """Check if role has admin/manager permissions (includes custom roles with equivalent)."""
    r = (role or "").lower()
    if r in ("admin", "manager"):
        return True
    # Custom roles: check via table if needed; for now only built-in manager counts
    return False




def is_superadmin(
    sub: str,
    user_pool_id: str,
    region: str = "us-east-1",
) -> bool:
    """
    Check if user (by sub) is in Cognito superadmin group.
    Returns True if sub is in superadmin group, False otherwise.
    """
    if not sub or not user_pool_id:
        return False
    try:
        import boto3

        client = boto3.client("cognito-idp", region_name=region)
        resp = client.admin_list_groups_for_user(
            UserPoolId=user_pool_id,
            Username=sub,
        )
        for g in resp.get("Groups", []):
            if (g.get("GroupName") or "").lower() == "superadmin":
                return True
        return False
    except Exception:
        return False
