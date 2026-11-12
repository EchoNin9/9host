"""
Tests for RequestContext (T-02): local JWKS verification, TUSER site_token,
superadmin impersonation (Bug #5), secret caching (Bug #7), and the safe 500
error boundary + Decimal serialization (Bug #8).
"""

import json
import sys
import time
import types
from decimal import Decimal

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import request_context as rc
import secrets_cache

REGION = "us-east-1"
POOL_ID = "us-east-1_dummy"  # matches conftest USER_POOL_ID
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{POOL_ID}"
KID = "test-kid-1"
JWT_SECRET = "tuser-test-secret"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def seams(monkeypatch, rsa_key):
    """Patch JWKS fetch + Secrets Manager fetch; reset module caches."""
    rc.clear_jwks_cache()
    secrets_cache.clear_cache()

    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rsa_key.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    calls = {"jwks": 0, "secret": 0}

    def fake_fetch_jwks(url):
        assert url == f"{ISSUER}/.well-known/jwks.json"
        calls["jwks"] += 1
        return {"keys": [jwk]}

    def fake_fetch_secret(secret_id):
        calls["secret"] += 1
        if "stripe" in secret_id:
            return json.dumps({"secret_key": "sk_test_1", "price_pro": "price_p"})
        return JWT_SECRET

    monkeypatch.setattr(rc, "_fetch_jwks", fake_fetch_jwks)
    monkeypatch.setattr(secrets_cache, "_fetch_secret_string", fake_fetch_secret)
    yield calls
    rc.clear_jwks_cache()
    secrets_cache.clear_cache()


def cognito_token(key, sub="sub-123", groups=None, **overrides):
    now = int(time.time())
    claims = {
        "sub": sub,
        "iss": ISSUER,
        "token_use": "access",
        "client_id": "client-abc",
        "iat": now,
        "exp": now + 3600,
    }
    if groups is not None:
        claims["cognito:groups"] = groups
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": KID})


def tuser_token(username="alice", tenant_slug="acme", role="editor", secret=JWT_SECRET):
    now = int(time.time())
    payload = {
        "username": username,
        "tenant_slug": tenant_slug,
        "role": role,
        "user_type": "tenant_user",
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def make_event(token=None, headers=None, path="/api/tenant", method="GET"):
    h = {"host": "stage.echo9.net"}  # platform host => no tenant from subdomain
    if token:
        h["authorization"] = f"Bearer {token}"
    h.update(headers or {})
    return {
        "rawPath": path,
        "headers": h,
        "requestContext": {"requestId": "req-abc-123", "http": {"method": method}},
    }


def put_member(table, tenant_slug, sub, role):
    table.put_item(
        Item={
            "pk": f"TENANT#{tenant_slug}",
            "sk": f"USER#{sub}#PROFILE",
            "gsi1pk": f"USER#{sub}",
            "gsi1sk": f"TENANT#{tenant_slug}#PROFILE",
            "role": role,
        }
    )


@pytest.fixture
def handler_module():
    """Import api/handler.py. ``templates/base_layout.py`` uses Python 3.12-only f-string
    syntax (Lambda runs 3.12; the test venv is 3.11), so stub ``templates`` if needed and
    drop every module imported here afterwards."""
    before = set(sys.modules)
    try:
        import templates  # noqa: F401
    except SyntaxError:
        for name in list(sys.modules):
            if name == "templates" or name.startswith("templates."):
                sys.modules.pop(name)
        stub = types.ModuleType("templates")
        stub.get_renderer = lambda *a, **k: None
        base = types.ModuleType("templates.base_layout")
        base.escape_html = base.media_url = base.nav_links = lambda *a, **k: ""
        stub.base_layout = base
        sys.modules["templates"] = stub
        sys.modules["templates.base_layout"] = base
    import handler

    yield handler
    for name in set(sys.modules) - before:
        sys.modules.pop(name, None)


# ---------------------------------------------------------------------------
# Cognito via local JWKS
# ---------------------------------------------------------------------------


class TestCognitoLocalJwks:
    def test_valid_token_yields_cognito_principal(self, rsa_key, seams):
        p = rc.authenticate(make_event(cognito_token(rsa_key)))
        assert p == rc.Principal(kind="cognito", identifier="sub-123", email=None, is_superadmin=False)

    def test_jwks_cached_for_one_hour(self, rsa_key, seams, monkeypatch):
        tok = cognito_token(rsa_key)
        rc.authenticate(make_event(tok))
        rc.authenticate(make_event(tok))
        assert seams["jwks"] == 1
        base = time.time()
        monkeypatch.setattr(rc, "_clock", lambda: base + rc.JWKS_TTL_SECONDS + 1)
        rc.authenticate(make_event(tok))
        assert seams["jwks"] == 2

    def test_superadmin_group_claim(self, rsa_key):
        p = rc.authenticate(make_event(cognito_token(rsa_key, groups=["SuperAdmin"])))
        assert p.is_superadmin is True

    def test_does_not_call_cognito_get_user(self, rsa_key, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("get_user must not be called when JWKS is configured")

        monkeypatch.setattr(rc, "_cognito_principal_via_get_user", boom)
        assert rc.authenticate(make_event(cognito_token(rsa_key))) is not None

    @pytest.mark.parametrize(
        "overrides",
        [
            {"exp": int(time.time()) - 10},
            {"iss": "https://cognito-idp.us-east-1.amazonaws.com/other_pool"},
            {"token_use": "id"},
        ],
    )
    def test_invalid_claims_rejected(self, rsa_key, overrides):
        assert rc.authenticate(make_event(cognito_token(rsa_key, **overrides))) is None

    def test_wrong_signing_key_rejected(self):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        assert rc.authenticate(make_event(cognito_token(other))) is None

    def test_garbage_token_rejected(self):
        assert rc.authenticate(make_event("not-a-jwt")) is None

    def test_falls_back_to_get_user_when_pool_unconfigured(self, rsa_key, monkeypatch, seams):
        monkeypatch.delenv("USER_POOL_ID")
        sentinel = rc.Principal(kind="cognito", identifier="dev", email=None, is_superadmin=False)
        monkeypatch.setattr(rc, "_cognito_principal_via_get_user", lambda t, pool, region: sentinel)
        assert rc.authenticate(make_event(cognito_token(rsa_key))) is sentinel
        assert seams["jwks"] == 0


# ---------------------------------------------------------------------------
# TenantUser (TUSER) site_token
# ---------------------------------------------------------------------------


class TestTenantUser:
    def test_valid_site_token(self, seams):
        p = rc.authenticate(make_event(tuser_token()))
        assert p.kind == "tuser"
        assert p.identifier == "alice"
        assert p.token_tenant_slug == "acme"
        assert p.token_role == "editor"
        assert p.is_superadmin is False

    def test_jwt_secret_cached(self, seams):
        tok = tuser_token()
        rc.authenticate(make_event(tok))
        rc.authenticate(make_event(tok))
        assert seams["secret"] == 1

    def test_wrong_secret_rejected(self):
        assert rc.authenticate(make_event(tuser_token(secret="nope"))) is None

    def test_role_from_token_in_own_tenant(self):
        ctx = rc.build_request_context(make_event(tuser_token(), {"x-tenant-slug": "acme"}))
        assert ctx.require_tenant_member(("editor",)) == ("acme", "editor")

    def test_locked_to_own_tenant(self):
        ctx = rc.build_request_context(make_event(tuser_token(), {"x-tenant-slug": "other"}))
        with pytest.raises(rc.HttpError) as e:
            ctx.require_tenant_member()
        assert e.value.status == 403

    def test_tuser_cannot_impersonate(self):
        ctx = rc.build_request_context(make_event(tuser_token(), {"x-impersonate-tenant": "other"}))
        assert ctx.is_impersonating is False


# ---------------------------------------------------------------------------
# Superadmin impersonation (Bug #5)
# ---------------------------------------------------------------------------


def respond_ok():
    return rc.respond(200, {})


class TestImpersonation:
    def test_header_sets_admin_role(self, rsa_key, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "TENANT#acme", "sk": "TENANT", "tier": "PRO"})
        tok = cognito_token(rsa_key, sub="super-1", groups=["superadmin"])
        ctx = rc.build_request_context(
            make_event(tok, {"x-impersonate-tenant": "Acme", "x-tenant-slug": "ignored"}),
            table=dynamodb_table,
        )
        assert ctx.tenant_slug == "acme"
        assert ctx.effective_role == "admin"
        assert ctx.is_impersonating is True
        assert ctx.require_tenant_member(("admin",)) == ("acme", "admin")

    def test_admin_tenant_path_sets_admin_role(self, rsa_key, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "TENANT#acme", "sk": "TENANT", "tier": "PRO"})
        tok = cognito_token(rsa_key, sub="super-1", groups=["superadmin"])
        ctx = rc.build_request_context(
            make_event(tok, path="/api/admin/tenants/acme/sites"), table=dynamodb_table
        )
        assert (ctx.tenant_slug, ctx.effective_role, ctx.is_impersonating) == ("acme", "admin", True)

    def test_impersonating_nonexistent_tenant_is_404(self, rsa_key, dynamodb_table):
        tok = cognito_token(rsa_key, sub="super-1", groups=["superadmin"])
        resp = rc.run_with_context(
            make_event(tok, {"x-impersonate-tenant": "ghost"}), lambda ctx: respond_ok(), table=dynamodb_table
        )
        assert resp["statusCode"] == 404
        assert json.loads(resp["body"]) == {"error": "Tenant not found"}

    def test_impersonation_reuses_loaded_tenant_item(self, rsa_key, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "TENANT#acme", "sk": "TENANT", "tier": "PRO"})
        tok = cognito_token(rsa_key, sub="super-1", groups=["superadmin"])
        ctx = rc.build_request_context(make_event(tok, {"x-impersonate-tenant": "acme"}), table=dynamodb_table)
        assert ctx.tenant_item["tier"] == "PRO"

    def test_non_superadmin_header_ignored(self, rsa_key, dynamodb_table):
        tok = cognito_token(rsa_key, sub="user-1")
        ctx = rc.build_request_context(
            make_event(tok, {"x-impersonate-tenant": "acme", "x-tenant-slug": "acme"}),
            table=dynamodb_table,
        )
        assert ctx.is_impersonating is False
        assert ctx.effective_role is None


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------


class TestRejections:
    def test_unauthenticated_returns_401(self):
        resp = rc.run_with_context(make_event(), lambda ctx: ctx.require_authenticated())
        assert resp["statusCode"] == 401
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_non_member_returns_403(self, rsa_key, dynamodb_table):
        ev = make_event(cognito_token(rsa_key, sub="stranger"), {"x-tenant-slug": "acme"})
        resp = rc.run_with_context(ev, lambda ctx: ctx.require_tenant_member(), table=dynamodb_table)
        assert resp["statusCode"] == 403
        assert "Not a member" in json.loads(resp["body"])["error"]

    def test_member_role_resolved_and_min_roles_enforced(self, rsa_key, dynamodb_table):
        put_member(dynamodb_table, "acme", "ed-1", "editor")
        ev = make_event(cognito_token(rsa_key, sub="ed-1"), {"x-tenant-slug": "acme"})
        ctx = rc.build_request_context(ev, table=dynamodb_table)
        assert ctx.require_tenant_member() == ("acme", "editor")
        with pytest.raises(rc.HttpError) as e:
            ctx.require_tenant_member(("admin", "manager"))
        assert e.value.status == 403

    def test_require_superadmin(self, rsa_key):
        ctx = rc.build_request_context(make_event(cognito_token(rsa_key)))
        with pytest.raises(rc.HttpError) as e:
            ctx.require_superadmin()
        assert e.value.status == 403

    def test_require_feature(self, rsa_key, dynamodb_table):
        dynamodb_table.put_item(Item={"pk": "TENANT#acme", "sk": "TENANT", "tier": "FREE"})
        dynamodb_table.put_item(
            Item={"pk": "TENANT#pro", "sk": "TENANT", "tier": "PRO", "module_overrides": {"branding": False}}
        )
        tok = cognito_token(rsa_key, groups=["superadmin"])
        free = rc.build_request_context(make_event(tok, {"x-impersonate-tenant": "acme"}), table=dynamodb_table)
        with pytest.raises(rc.HttpError):
            free.require_feature("custom_domains")
        free.require_feature("branding")
        pro = rc.build_request_context(make_event(tok, {"x-impersonate-tenant": "pro"}), table=dynamodb_table)
        pro.require_feature("custom_domains")
        with pytest.raises(rc.HttpError):
            pro.require_feature("branding")


# ---------------------------------------------------------------------------
# Error boundary + Decimal (Bug #8)
# ---------------------------------------------------------------------------


class TestErrorBoundary:
    def test_unhandled_exception_is_scrubbed(self, capsys):
        def handler(ctx):
            raise ValueError("secret internals /var/task/foo.py")

        resp = rc.run_with_context(make_event(), handler)
        assert resp["statusCode"] == 500
        body = json.loads(resp["body"])
        assert body == {"error": "Internal server error", "request_id": "req-abc-123"}
        assert "Traceback" not in resp["body"] and "secret internals" not in resp["body"]
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
        logged = capsys.readouterr().out
        assert "Traceback" in logged and "secret internals" in logged

    def test_decimal_serialized(self):
        resp = rc.run_with_context(
            make_event(),
            lambda ctx: {"statusCode": 200, "body": {"n": Decimal("3"), "f": Decimal("1.5"), "l": [Decimal("0")]}},
        )
        assert resp["statusCode"] == 200
        assert json.loads(resp["body"]) == {"n": 3, "f": 1.5, "l": [0]}
        assert '"n": 3,' in resp["body"]
        assert resp["headers"]["Content-Type"] == "application/json"
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"

    def test_lambda_handler_500_has_no_traceback(self, handler_module, monkeypatch, capsys):
        handler = handler_module

        def boom(event, context):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(handler, "_lambda_handler_impl", boom)
        resp = handler.lambda_handler(make_event(), None)
        assert resp["statusCode"] == 500
        body = json.loads(resp["body"])
        assert body == {"error": "Internal server error", "request_id": "req-abc-123"}
        assert "detail" not in body and "kaboom" not in resp["body"]
        assert "kaboom" in capsys.readouterr().out

    def test_handler_with_cors_serializes_decimal(self, handler_module):
        resp = handler_module._with_cors({"statusCode": 200, "body": {"size": Decimal("42")}})
        assert json.loads(resp["body"]) == {"size": 42}
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"


# ---------------------------------------------------------------------------
# Secret caching wired into helpers (Bug #7)
# ---------------------------------------------------------------------------


def test_stripe_config_uses_secret_cache(seams):
    import stripe_helpers

    assert stripe_helpers.get_stripe_api_key() == "sk_test_1"
    assert stripe_helpers.get_stripe_price_id("pro") == "price_p"
    assert seams["secret"] == 1
