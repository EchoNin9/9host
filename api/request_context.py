"""
RequestContext — single ingress gate for authenticated API requests (SPEC §3 Module 2).

    ctx = build_request_context(event)          # authenticate + resolve tenant/role once
    ctx.require_tenant_member(("admin", "manager"))

    run_with_context(event, lambda ctx: {...})  # error boundary + Decimal + CORS

Principals:
  - ``cognito``: Cognito access token verified locally against the user pool JWKS
    (RS256, module-cached for 1 hour). Falls back to ``cognito-idp.get_user`` only when
    ``USER_POOL_ID`` is unset (local dev) or RS256 support (``cryptography``) is missing.
  - ``tuser``: TenantUser ``site_token`` (HS256 / HMAC-SHA256) signed with the JWT secret
    from ``secrets_cache``.

Bug #5: a superadmin with ``X-Impersonate-Tenant`` (or on ``/api/admin/tenants/{slug}/*``)
gets ``tenant_slug=<slug>``, ``effective_role="admin"``, ``is_impersonating=True``.
Bug #8: ``run_with_context`` never leaks tracebacks; Decimal is serialized to int/float.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import traceback
import urllib.request
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Literal

import jwt

import secrets_cache

logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "300",
}

JWKS_TTL_SECONDS = 3600  # 1 hour

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$")
_ADMIN_TENANT_PATH_RE = re.compile(r"^/api/admin/tenants/([^/]+)(?:/|$)")
BUILTIN_ROLES = frozenset({"admin", "manager", "editor", "member"})


# ---------------------------------------------------------------------------
# Patchable seams for tests
# ---------------------------------------------------------------------------

_clock = time.time


def _fetch_jwks(url: str) -> dict:
    """Fetch a JWKS document over HTTPS."""
    with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - fixed https URL
        return json.loads(resp.read().decode("utf-8"))


_jwks_lock = threading.Lock()
_jwks_cache: dict[str, tuple[float, dict]] = {}  # url -> (expires_at, jwks)


def clear_jwks_cache() -> None:
    with _jwks_lock:
        _jwks_cache.clear()


def _get_jwks(url: str) -> dict:
    now = _clock()
    with _jwks_lock:
        hit = _jwks_cache.get(url)
        if hit and hit[0] > now:
            return hit[1]
    jwks = _fetch_jwks(url)
    with _jwks_lock:
        _jwks_cache[url] = (now + JWKS_TTL_SECONDS, jwks)
    return jwks


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class HttpError(Exception):
    """Raised by ``require_*`` guards; ``run_with_context`` renders it as JSON."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class Principal:
    kind: Literal["cognito", "tuser"]
    identifier: str  # Cognito sub or TUSER username
    email: str | None
    is_superadmin: bool
    token_tenant_slug: str | None = None
    token_role: str | None = None


@dataclass(frozen=True)
class RequestContext:
    event: dict
    principal: Principal | None
    tenant_slug: str | None
    effective_role: str | None  # "admin" | "manager" | "editor" | "member" | custom role
    is_impersonating: bool
    tenant_item: dict | None = None  # Cached tenant METADATA row when loaded
    _custom_permissions: dict | None = field(default=None, repr=False, compare=False)
    _table: Any = field(default=None, repr=False, compare=False)

    @property
    def method(self) -> str:
        e = self.event
        return ((e.get("requestContext") or {}).get("http", {}).get("method") or e.get("httpMethod") or "GET").upper()

    @property
    def path(self) -> str:
        return (self.event.get("rawPath") or self.event.get("path") or "").rstrip("/")

    def json_body(self) -> dict:
        """Parsed JSON object body; {} when missing or invalid."""
        raw = self.event.get("body")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw) if raw else None
            except ValueError:
                raw = None
        return raw if isinstance(raw, dict) else {}

    def query(self, name: str) -> str:
        return ((self.event.get("queryStringParameters") or {}).get(name) or "").strip()

    def require_authenticated(self) -> Principal:
        if self.principal is None:
            raise HttpError(401, "Unauthorized. Provide Authorization: Bearer <access_token>.")
        return self.principal

    def require_superadmin(self) -> Principal:
        principal = self.require_authenticated()
        if not principal.is_superadmin:
            raise HttpError(403, "Forbidden. Superadmin required.")
        return principal

    def require_tenant_member(self, min_roles: tuple[str, ...] | None = None) -> tuple[str, str]:
        """Return ``(tenant_slug, effective_role)`` or raise 400/401/403."""
        principal = self.require_authenticated()
        if not self.tenant_slug:
            raise HttpError(400, "Missing tenant. Use subdomain or X-Tenant-Slug header.")
        if not self.effective_role:
            if principal.kind == "tuser":
                raise HttpError(403, "Forbidden. Tenant user is locked to their tenant.")
            raise HttpError(403, "Forbidden. Not a member of this tenant.")
        if min_roles and self.effective_role not in {r.lower() for r in min_roles}:
            raise HttpError(403, f"Forbidden. Requires role: {', '.join(min_roles)}.")
        return self.tenant_slug, self.effective_role

    def require_permission(self, module: str, roles: tuple[str, ...]) -> tuple[str, str]:
        """Like ``require_tenant_member(roles)``, but a tenant-defined CustomRole
        (``ROLE#{name}``, T-15) also passes when its ``permissions[module]`` is true.
        Built-in roles are checked against ``roles`` only; the ROLE# row is read at most once."""
        tenant_slug, role = self.require_tenant_member()
        if role in {r.lower() for r in roles}:
            return tenant_slug, role
        if role not in BUILTIN_ROLES:
            perms = self._custom_permissions
            if perms is None:
                item = _get_table(self._table).get_item(
                    Key={"pk": f"TENANT#{tenant_slug}", "sk": f"ROLE#{role}"}
                ).get("Item") or {}
                perms = item.get("permissions") if isinstance(item.get("permissions"), dict) else {}
                object.__setattr__(self, "_custom_permissions", perms)
            if perms.get(module) is True:
                return tenant_slug, role
        raise HttpError(403, f"Forbidden. Requires role: {', '.join(roles)} or '{module}' permission.")

    def require_feature(self, feature_key: str) -> None:
        """Raise 403 unless the tenant's tier (+ module_overrides) grants ``feature_key``."""
        from tier_config import tier_has_feature, tier_has_module

        if not self.tenant_slug:
            raise HttpError(400, "Missing tenant. Use subdomain or X-Tenant-Slug header.")
        item = self.tenant_item
        if item is None:
            item = _load_tenant_item(self._table, self.tenant_slug) or {}
            object.__setattr__(self, "tenant_item", item)
        overrides = item.get("module_overrides") or {}
        if feature_key in overrides:
            allowed = bool(overrides[feature_key])
        else:
            tier = (item.get("tier") or "FREE").upper()
            allowed = tier_has_feature(tier, feature_key) or tier_has_module(tier, feature_key)
        if not allowed:
            raise HttpError(403, f"Feature '{feature_key}' is not available on this plan.")


# ---------------------------------------------------------------------------
# Header / tenant helpers
# ---------------------------------------------------------------------------


def _get_header(event: dict, name: str) -> str:
    headers = event.get("headers") or {}
    key_lower = name.lower()
    if isinstance(headers, dict):
        for k, v in headers.items():
            if (k or "").lower() == key_lower:
                return (v or "").strip()
        return ""
    for h in headers:
        if (h.get("key") or h.get("Key") or "").lower() == key_lower:
            return (h.get("value") or h.get("Value") or "").strip()
    return ""


def _bearer_token(event: dict) -> str | None:
    auth = _get_header(event, "authorization")
    if not auth.startswith("Bearer "):
        return None
    return auth[7:].strip() or None


def impersonated_tenant_slug(event: dict) -> str | None:
    """Tenant requested via ``X-Impersonate-Tenant`` or ``/api/admin/tenants/{slug}/*``."""
    slug = _get_header(event, "x-impersonate-tenant").lower()
    if not slug:
        path = event.get("rawPath") or event.get("path") or ""
        m = _ADMIN_TENANT_PATH_RE.match(path)
        slug = (m.group(1).lower() if m else "")
    return slug if slug and _SLUG_RE.match(slug) else None


def _get_table(table):
    if table is not None:
        return table
    import boto3

    return boto3.resource("dynamodb").Table(os.environ.get("DYNAMODB_TABLE", ""))


def _load_tenant_item(table, tenant_slug: str) -> dict | None:
    resp = _get_table(table).get_item(Key={"pk": f"TENANT#{tenant_slug}", "sk": "TENANT"})
    return resp.get("Item")


def _member_role(table, tenant_slug: str, sub: str) -> str | None:
    resp = _get_table(table).get_item(
        Key={"pk": f"TENANT#{tenant_slug}", "sk": f"USER#{sub}#PROFILE"}
    )
    item = resp.get("Item")
    if not item:
        return None
    return (item.get("role") or "member").lower()


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------


def _region() -> str:
    return os.environ.get("AWS_REGION", "us-east-1")


def _verify_cognito_local(token: str, user_pool_id: str, region: str) -> dict | None:
    """Verify a Cognito access token against the cached JWKS. Returns claims or None."""
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        jwks = _get_jwks(f"{issuer}/.well-known/jwks.json")
        jwk = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if not jwk:
            return None
        key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False, "require": ["exp", "iss", "sub"]},
        )
    except Exception as exc:  # noqa: BLE001 - any failure => unauthenticated
        logger.info("request_context: cognito token rejected: %s", exc)
        return None
    if claims.get("token_use") != "access":
        return None
    return claims


def _cognito_principal_via_get_user(token: str, user_pool_id: str, region: str) -> Principal | None:
    """Local-dev fallback: remote ``cognito-idp.get_user`` (one network call per request)."""
    import boto3

    try:
        resp = boto3.client("cognito-idp", region_name=region).get_user(AccessToken=token)
    except Exception:  # noqa: BLE001
        return None
    attrs = {a.get("Name"): a.get("Value") for a in resp.get("UserAttributes", [])}
    sub = attrs.get("sub") or resp.get("Username", "")
    if not sub:
        return None
    return Principal(
        kind="cognito",
        identifier=sub,
        email=attrs.get("email"),
        is_superadmin=_in_superadmin_group(sub, user_pool_id, region),
    )


def _in_superadmin_group(sub: str, user_pool_id: str, region: str) -> bool:
    """Local-dev fallback only: Cognito group lookup (no verified ``cognito:groups`` claim)."""
    if not user_pool_id:
        return False
    import boto3

    try:
        resp = boto3.client("cognito-idp", region_name=region).admin_list_groups_for_user(
            UserPoolId=user_pool_id, Username=sub
        )
    except Exception:  # noqa: BLE001
        return False
    return any((g.get("GroupName") or "").lower() == "superadmin" for g in resp.get("Groups", []))


def _verify_tuser(token: str) -> Principal | None:
    secret = secrets_cache.get_secret_string(os.environ.get("JWT_SECRET_ARN"))
    if not secret or secret == "REPLACE_ME":
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:  # noqa: BLE001
        return None
    if payload.get("user_type") != "tenant_user" or not payload.get("username"):
        return None
    return Principal(
        kind="tuser",
        identifier=payload["username"],
        email=None,
        is_superadmin=False,
        token_tenant_slug=(payload.get("tenant_slug") or "").lower() or None,
        token_role=(payload.get("role") or "member").lower(),
    )


def authenticate(event: dict, region: str | None = None) -> Principal | None:
    """Resolve the Bearer token to a Principal, or None if missing/invalid."""
    token = _bearer_token(event)
    if not token:
        return None
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except Exception:  # noqa: BLE001 - opaque / malformed token
        alg = None
    if alg == "HS256":
        return _verify_tuser(token)

    region = region or _region()
    user_pool_id = os.environ.get("USER_POOL_ID", "")
    if not user_pool_id or not jwt.algorithms.has_crypto:
        if user_pool_id:
            logger.warning("request_context: RS256 unavailable (no 'cryptography'); using get_user")
        return _cognito_principal_via_get_user(token, user_pool_id, region)

    claims = _verify_cognito_local(token, user_pool_id, region)
    if not claims:
        return None
    groups = [str(g).lower() for g in (claims.get("cognito:groups") or [])]
    return Principal(
        kind="cognito",
        identifier=claims["sub"],
        email=claims.get("email"),
        is_superadmin="superadmin" in groups,
    )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_request_context(event: dict, table=None) -> RequestContext:
    """Authenticate, then resolve tenant + effective role exactly once."""
    from middleware import extract_tenant_slug

    principal = authenticate(event)

    impersonate = impersonated_tenant_slug(event) if principal and principal.is_superadmin else None
    if impersonate:
        tenant_item = _load_tenant_item(table, impersonate)
        if not tenant_item:
            raise HttpError(404, "Tenant not found")
        return RequestContext(
            event=event,
            principal=principal,
            tenant_slug=impersonate,
            effective_role="admin",
            is_impersonating=True,
            tenant_item=tenant_item,
            _table=table,
        )

    tenant_slug = extract_tenant_slug(event, domains=os.environ.get("DOMAINS"))
    role = None
    if principal and tenant_slug:
        if principal.kind == "tuser":
            role = principal.token_role if principal.token_tenant_slug == tenant_slug else None
        else:
            role = _member_role(table, tenant_slug, principal.identifier)
    return RequestContext(
        event=event,
        principal=principal,
        tenant_slug=tenant_slug,
        effective_role=role,
        is_impersonating=False,
        _table=table,
    )


# ---------------------------------------------------------------------------
# Response helpers + error boundary (Bug #8)
# ---------------------------------------------------------------------------


def _json_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def json_dumps(obj) -> str:
    """``json.dumps`` that serializes DynamoDB ``Decimal`` as int/float."""
    return json.dumps(obj, default=_json_default)


def respond(status: int, body: dict | None = None) -> dict:
    """Handler response; ``body=None`` gives an empty body (e.g. 204)."""
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": "" if body is None else json_dumps(body),
    }


def finalize_response(resp: dict) -> dict:
    """Serialize non-string bodies (Decimal-safe) and merge CORS headers."""
    body = resp.get("body")
    headers = dict(resp.get("headers") or {})
    if body is not None and not isinstance(body, str):
        resp["body"] = json_dumps(body)
        headers.setdefault("Content-Type", "application/json")
    resp["headers"] = {**CORS_HEADERS, **headers}
    return resp


def _request_id(event: dict) -> str:
    return (event.get("requestContext") or {}).get("requestId") or str(uuid.uuid4())


def internal_error_response(event: dict, exc: BaseException) -> dict:
    """Log the full exception to CloudWatch; return a scrubbed 500."""
    request_id = _request_id(event)
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(f"[9host] 500 request_id={request_id}: {type(exc).__name__}: {exc}\n{tb}")
    return {
        "statusCode": 500,
        "headers": {**CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps({"error": "Internal server error", "request_id": request_id}),
    }


def run_with_context(
    event: dict,
    handler_fn: Callable[[RequestContext], dict],
    table=None,
) -> dict:
    """Build a RequestContext, run ``handler_fn(ctx)``, and apply the error boundary."""
    try:
        ctx = build_request_context(event, table=table)
        resp = handler_fn(ctx)
    except HttpError as e:
        resp = {"statusCode": e.status, "body": {"error": e.message}}
    except Exception as e:  # noqa: BLE001 - error boundary
        return internal_error_response(event, e)
    try:
        return finalize_response(resp)
    except Exception as e:  # noqa: BLE001 - e.g. unserializable body
        return internal_error_response(event, e)
