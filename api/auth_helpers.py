"""
Auth helpers for 9host API.

Supports dual-mode auth: Cognito (GetUser) and custom JWT (tenant_user).
"""

import os

import jwt


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
    """Fetch JWT signing key from Secrets Manager."""
    import boto3

    arn = os.environ.get("JWT_SECRET_ARN")
    if not arn:
        return None
    try:
        client = boto3.client("secretsmanager")
        resp = client.get_secret_value(SecretId=arn)
        return resp.get("SecretString", "").strip() or None
    except Exception:
        return None


def get_auth_context(event: dict, region: str = "us-east-1") -> dict | None:
    """
    Extract auth identity from Bearer token. Dual-mode: Cognito or custom JWT.

    Returns:
      - Cognito: {"user_type": "cognito", "sub": str}
      - Tenant user: {"user_type": "tenant_user", "username": str, "tenant_slug": str, "role": str}
      - None if missing/invalid
    """
    import boto3

    auth = _get_auth_header(event)
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None

    # Try Cognito first
    try:
        client = boto3.client("cognito-idp", region_name=region)
        resp = client.get_user(AccessToken=token)
        for attr in resp.get("UserAttributes", []):
            if attr.get("Name") == "sub":
                return {"user_type": "cognito", "sub": attr.get("Value")}
        return {"user_type": "cognito", "sub": resp.get("Username", "")}
    except Exception:
        pass

    # Try custom JWT (tenant_user)
    secret = _get_jwt_secret()
    if not secret or secret == "REPLACE_ME":
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        if payload.get("user_type") == "tenant_user":
            return {
                "user_type": "tenant_user",
                "username": payload.get("username", ""),
                "tenant_slug": payload.get("tenant_slug", ""),
                "role": payload.get("role", "member"),
            }
    except Exception:
        pass

    return None


def get_sub_from_access_token(event: dict, region: str = "us-east-1") -> str | None:
    """
    Extract Cognito sub from Bearer token via GetUser.
    Returns sub or None if missing/invalid. Does not support tenant_user JWT.
    """
    ctx = get_auth_context(event, region)
    if ctx and ctx.get("user_type") == "cognito":
        return ctx.get("sub")
    return None


def get_user_role_in_tenant(table, sub: str, tenant_slug: str) -> str | None:
    """
    Get user's role in tenant from profile. Returns role (admin|manager|editor|member)
    or None if not a member.
    """
    from dynamodb_helpers import get_user_profile_item

    key = get_user_profile_item(tenant_slug, sub)
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return None
    return (item.get("role") or "member").lower()


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
    from dynamodb_helpers import query_tenants_for_user

    params = query_tenants_for_user(sub)
    resp = table.query(**params)
    for item in resp.get("Items", []):
        if item.get("gsi1sk") == f"TENANT#{tenant_slug}#PROFILE":
            role = (item.get("role") or "member").lower()
            return True, sub, role, True

    return None, {
        "statusCode": 403,
        "body": '{"error": "Forbidden. Not a member of this tenant."}',
    }


def require_tenant_admin_or_manager(table, sub: str, tenant_slug: str) -> tuple[bool, str | None]:
    """
    Require admin or manager role for tenant. Returns (True, None) if ok,
    (False, error_message) if not.
    """
    role = get_user_role_in_tenant(table, sub, tenant_slug)
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
