"""
Handler integration tests (T-09): full ``handler.lambda_handler`` round-trips against the moto
9host-main table, with real RequestContext auth (RS256 Cognito tokens via a patched JWKS fetch,
HS256 TUSER site tokens via a patched secret fetch).

Covers Bug #3 (site listing never reads content rows), Bug #4 (media delete storage floor),
Bug #5 (impersonating superadmin edits content), Bug #1 (/api/tenant/default-site removed),
the admin/tenant CRUD unification, host-mapping hygiene, /api/admin/edge-kvs and the
sanitized 500 boundary (Bug #8).
"""

import json
import time

import boto3
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import handler
import request_context as rc
import secrets_cache
import site_storage
from tenant_store import DynamoDBTenantStore, entity_keys_domain

ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_dummy"  # conftest USER_POOL_ID
KID = "kid-1"
JWT_SECRET = "integration-test-tuser-secret-0123456789"


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def api(dynamodb_table, rsa_key, monkeypatch):
    """Seeded tenant 'acme' (PRO) with an admin member; S3 media bucket; auth seams patched."""
    rc.clear_jwks_cache()
    secrets_cache.clear_cache()
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rsa_key.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    monkeypatch.setattr(rc, "_fetch_jwks", lambda url: {"keys": [jwk]})
    monkeypatch.setattr(secrets_cache, "_fetch_secret_string", lambda sid: JWT_SECRET)
    monkeypatch.delenv("SITE_HOSTS_KVS_ARN", raising=False)

    removed: list[str] = []
    monkeypatch.setattr(site_storage, "delete_host_mapping", removed.append)
    storage = site_storage.InMemorySiteStorage()
    monkeypatch.setattr(site_storage, "default_storage", lambda: storage)

    dynamodb_table.put_item(Item={"pk": "TENANT#acme", "sk": "TENANT", "tier": "PRO", "name": "Acme"})
    DynamoDBTenantStore(dynamodb_table).put_member("acme", {"sub": "owner-1", "role": "admin", "name": "Owner"})
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="9host-media")
    yield type("Api", (), {"table": dynamodb_table, "key": rsa_key, "removed_mappings": removed, "storage": storage})
    rc.clear_jwks_cache()
    secrets_cache.clear_cache()


def cognito(key, sub, groups=None):
    now = int(time.time())
    claims = {"sub": sub, "iss": ISSUER, "token_use": "access", "iat": now, "exp": now + 3600}
    if groups:
        claims["cognito:groups"] = groups
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": KID})


def tuser(username="ed", role="member", tenant="acme"):
    now = int(time.time())
    return jwt.encode(
        {"username": username, "tenant_slug": tenant, "role": role, "user_type": "tenant_user", "exp": now + 3600},
        JWT_SECRET, algorithm="HS256",
    )


def call(method, path, token=None, tenant="acme", body=None, headers=None, query=None):
    h = {"x-tenant-slug": tenant} if tenant else {}
    if token:
        h["authorization"] = f"Bearer {token}"
    h.update(headers or {})
    event = {"rawPath": path, "requestContext": {"http": {"method": method}, "requestId": "req-9"}, "headers": h}
    if body is not None:
        event["body"] = json.dumps(body)
    if query:
        event["queryStringParameters"] = query
    resp = handler.lambda_handler(event, None)
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
    return resp["statusCode"], (json.loads(resp["body"]) if resp.get("body") else None)


def owner(api):
    return cognito(api.key, "owner-1")


def superadmin(api):
    return cognito(api.key, "super-1", ["superadmin"])


def create_site(api, token=None, slug="band", headers=None):
    code, body = call("POST", "/api/tenant/sites", token or owner(api), body={"name": "Band", "slug": slug}, headers=headers)
    assert code == 201, body
    return body["site"]["id"]


# ---------------------------------------------------------------------------
# Auth: 401 / 403 / Bug #5 impersonation
# ---------------------------------------------------------------------------


def test_unauthenticated_gets_401(api):
    assert call("GET", "/api/tenant/sites")[0] == 401
    assert call("GET", "/api/tenant/users")[0] == 401


def test_non_member_gets_403(api):
    stranger = cognito(api.key, "stranger-1")
    code, body = call("GET", "/api/tenant/sites", stranger)
    assert code == 403 and "Not a member" in body["error"]
    assert call("POST", "/api/tenant/sites", stranger, body={"name": "x"})[0] == 403


def test_superadmin_impersonating_tenant_crud_all_content(api):
    """Bug #5: X-Impersonate-Tenant superadmin (not a member) creates/edits/deletes everything."""
    sa = superadmin(api)
    imp = {"x-impersonate-tenant": "acme"}
    site_id = create_site(api, sa, headers=imp)
    base = f"/api/tenant/sites/{site_id}"

    for entity, key, create, update, item_id_field in [
        ("pages", "page", {"path": "about", "title": "About", "status": "PUBLISHED"}, {"title": "About us"}, "path"),
        ("posts", "post", {"slug": "hello", "title": "Hello"}, {"title": "Hello again", "slug": "hello-2"}, "id"),
        ("events", "event", {"title": "Gig", "event_date": "2026-12-01"}, {"venue": "Hall"}, "id"),
    ]:
        code, body = call("POST", f"{base}/{entity}", sa, body=create, headers=imp)
        assert code == 201, (entity, body)
        item_id = body[key][item_id_field]
        code, body = call("PUT", f"{base}/{entity}/{item_id}", sa, body=update, headers=imp)
        assert code == 200, (entity, body)
        assert all(body[key][k] == v for k, v in update.items())
        code, body = call("GET", f"{base}/{entity}", sa, headers=imp)
        assert code == 200 and len(body[entity]) == 1
        assert call("DELETE", f"{base}/{entity}/{item_id}", sa, headers=imp) == (204, None)
        assert call("GET", f"{base}/{entity}/{item_id}", sa, headers=imp)[0] == 404

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.put_object(Bucket="9host-media", Key=f"acme/{site_id}/a.png", Body=b"x" * 100)
    code, body = call("POST", f"{base}/media", sa, body={"s3_key": f"acme/{site_id}/a.png", "caption": "A"}, headers=imp)
    assert code == 201, body
    media_id = body["media"]["id"]
    code, body = call("PUT", f"{base}/media/{media_id}", sa, body={"caption": "B", "sort_order": "3"}, headers=imp)
    assert code == 200 and body["media"]["caption"] == "B" and body["media"]["sort_order"] == 3
    assert call("DELETE", f"{base}/media/{media_id}", sa, headers=imp) == (204, None)


def test_superadmin_on_admin_path_edits_content(api):
    site_id = create_site(api)
    code, body = call("POST", f"/api/admin/tenants/acme/sites/{site_id}/pages", superadmin(api), tenant=None,
                      body={"path": "home", "title": "Home"})
    assert code == 201 and body["page"]["path"] == "home"
    code, body = call("GET", f"/api/tenant/sites/{site_id}/pages/home", owner(api))
    assert code == 200 and body["page"]["title"] == "Home"


def test_legacy_editor_role_is_treated_as_member(api):
    """T-27: built-in 'editor' was dropped; a stored/issued 'editor' resolves to 'member'."""
    site_id = create_site(api)
    ed = tuser(role="editor")
    base = f"/api/tenant/sites/{site_id}/pages"
    assert call("POST", base, ed, body={"path": "news", "title": "News"})[0] == 403
    assert call("GET", base, ed)[0] == 200
    assert call("GET", "/api/tenant/sites", ed)[0] == 200

    assert call("GET", "/api/tenant/users", ed)[0] == 403
    assert call("GET", "/api/tenant/tusers", ed)[0] == 403
    assert call("POST", "/api/tenant/tusers", ed, body={"username": "x", "password": "password1"})[0] == 403
    assert call("GET", "/api/tenant/roles", ed)[0] == 403
    assert call("POST", "/api/tenant/sites", ed, body={"name": "Nope"})[0] == 403
    # A TUSER token is locked to its own tenant.
    assert call("GET", "/api/tenant/sites", tuser(tenant="other"))[0] == 403


def test_member_role_cannot_edit_content(api):
    site_id = create_site(api)
    member = tuser(role="member")
    assert call("GET", f"/api/tenant/sites/{site_id}/pages", member)[0] == 200
    assert call("POST", f"/api/tenant/sites/{site_id}/pages", member, body={"path": "x"})[0] == 403


# ---------------------------------------------------------------------------
# Bug #3: GET /api/tenant/sites returns only sites, never reads content rows
# ---------------------------------------------------------------------------


def test_list_sites_only_sites_and_consistent_after_crud(api, monkeypatch):
    tok = owner(api)
    a = create_site(api, slug="alpha")
    b = create_site(api, slug="beta")
    for site_id in (a, b):
        call("POST", f"/api/tenant/sites/{site_id}/pages", tok, body={"path": "home"})
        call("POST", f"/api/tenant/sites/{site_id}/posts", tok, body={"slug": "p1"})
        call("POST", f"/api/tenant/sites/{site_id}/events", tok, body={"title": "e"})

    # The first-ever list does TenantStore's one-time lazy SITE# -> SITE_META# backfill (T-03);
    # every later list reads only SITE_META#.
    call("GET", "/api/tenant/sites", tok)
    prefixes: list[str] = []
    real = DynamoDBTenantStore._query_prefix
    monkeypatch.setattr(
        DynamoDBTenantStore, "_query_prefix", lambda self, pk, p: prefixes.append(p) or real(self, pk, p)
    )
    code, body = call("GET", "/api/tenant/sites", tok)
    assert code == 200
    assert sorted(s["slug"] for s in body["sites"]) == ["alpha", "beta"]
    assert set(body["sites"][0]) >= {"id", "name", "slug", "status", "template_id", "published_version"}
    assert not any(p.startswith("SITE#") for p in prefixes), prefixes

    assert call("PUT", f"/api/tenant/sites/{a}", tok, body={"name": "Alpha 2", "slug": "alpha-2"})[0] == 200
    sites = {s["id"]: s for s in call("GET", "/api/tenant/sites", tok)[1]["sites"]}
    assert sites[a]["name"] == "Alpha 2" and sites[a]["slug"] == "alpha-2"

    assert call("DELETE", f"/api/tenant/sites/{b}", tok) == (204, None)
    prefixes.clear()
    assert [s["id"] for s in call("GET", "/api/tenant/sites", tok)[1]["sites"]] == [a]
    assert prefixes == ["SITE_META#"]
    assert call("GET", f"/api/tenant/sites/{b}/pages", tok)[0] == 404
    # Cascade removed the deleted site's content rows.
    assert DynamoDBTenantStore(api.table).list_content("acme", b, "PAGE") == []


def test_slug_conflicts(api):
    create_site(api, slug="taken")
    tok = owner(api)
    assert call("POST", "/api/tenant/sites", tok, body={"name": "X", "slug": "taken"})[0] == 409
    assert call("POST", "/api/tenant/sites", tok, body={"name": "X", "slug": "acme"})[0] == 409  # tenant slug


# ---------------------------------------------------------------------------
# Host-mapping hygiene
# ---------------------------------------------------------------------------


def test_slug_change_and_delete_remove_kvs_mappings(api):
    tok = owner(api)
    site_id = create_site(api, slug="old-slug")
    call("PUT", f"/api/tenant/sites/{site_id}", tok, body={"slug": "new-slug"})
    assert api.removed_mappings == ["old-slug.echo9.net"]

    api.table.put_item(Item={
        "pk": "TENANT#acme", "sk": "DOMAIN#myband.com", "gsi2pk": "DOMAIN#myband.com", "gsi2sk": "TENANT#acme",
        "site_id": site_id, "status": "ACTIVE",
    })
    assert call("DELETE", f"/api/tenant/sites/{site_id}", tok) == (204, None)
    assert set(api.removed_mappings[1:]) == {"myband.com", "new-slug.echo9.net"}
    assert api.table.get_item(Key={"pk": "TENANT#acme", "sk": "DOMAIN#myband.com"}).get("Item") is None


# ---------------------------------------------------------------------------
# T-14: S3 cleanup on site / tenant delete; migration marker on tenant create
# ---------------------------------------------------------------------------


def _seed_files(storage, *prefixes):
    for prefix in prefixes:
        for key in ("published/current/index.html", "draft/index.html"):
            storage._put(f"{prefix}{key}", b"x", "text/html")


def test_site_delete_empties_storage_prefix(api):
    tok = owner(api)
    gone, keep = create_site(api, slug="gone"), create_site(api, slug="keep")
    _seed_files(api.storage, f"acme/{gone}/", f"acme/{keep}/", f"acme2/{gone}/")
    assert call("DELETE", f"/api/tenant/sites/{gone}", tok) == (204, None)
    assert not any(k.startswith(f"acme/{gone}/") for k in api.storage.objects)
    assert any(k.startswith(f"acme/{keep}/") for k in api.storage.objects)
    assert any(k.startswith(f"acme2/{gone}/") for k in api.storage.objects)  # other tenant untouched


def test_tenant_delete_empties_storage_prefix(api):
    site_id = create_site(api)
    _seed_files(api.storage, f"acme/{site_id}/", "acme-other/s1/")
    api.storage._put("acme/default.json", b"{}", "application/json")
    assert call("DELETE", "/api/admin/tenants/acme", superadmin(api), tenant=None) == (204, None)
    assert sorted(api.storage.objects) == ["acme-other/s1/draft/index.html", "acme-other/s1/published/current/index.html"]


def test_new_tenant_first_list_sites_skips_legacy_query(api, monkeypatch):
    tok = cognito(api.key, "founder-1")
    code, body = call("POST", "/api/tenants", tok, tenant=None, body={"slug": "fresh"})
    assert code == 201, body
    prefixes: list[str] = []
    real = DynamoDBTenantStore._query_prefix
    monkeypatch.setattr(
        DynamoDBTenantStore, "_query_prefix", lambda self, pk, p: prefixes.append(p) or real(self, pk, p)
    )
    code, body = call("GET", "/api/tenant/sites", tok, tenant="fresh")
    assert code == 200 and body["sites"] == []
    assert not any(p.startswith("SITE#") for p in prefixes), prefixes


def test_admin_created_tenant_has_migration_marker(api, monkeypatch):
    code, body = call("POST", "/api/admin/tenants", superadmin(api), tenant=None, body={"slug": "fresh2"})
    assert code == 201, body
    assert api.table.get_item(Key={"pk": "TENANT#fresh2", "sk": "MIGRATION#SITE_META"}).get("Item")


# ---------------------------------------------------------------------------
# Bug #4: media delete decrements storage with a floor at 0
# ---------------------------------------------------------------------------


def _storage(api):
    return int(api.table.get_item(Key={"pk": "TENANT#acme", "sk": "TENANT"})["Item"].get("storage_used_bytes", 0))


def test_media_storage_accounting_floor_at_zero(api):
    tok = owner(api)
    site_id = create_site(api)
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.put_object(Bucket="9host-media", Key=f"acme/{site_id}/big.jpg", Body=b"x" * 500)
    code, body = call("POST", f"/api/tenant/sites/{site_id}/media", tok, body={"s3_key": f"acme/{site_id}/big.jpg"})
    assert code == 201 and _storage(api) == 500
    media_id = body["media"]["id"]

    api.table.update_item(
        Key={"pk": "TENANT#acme", "sk": "TENANT"}, UpdateExpression="SET storage_used_bytes = :v",
        ExpressionAttributeValues={":v": 120},
    )
    assert call("DELETE", f"/api/tenant/sites/{site_id}/media/{media_id}", tok) == (204, None)
    assert _storage(api) == 0
    assert "Contents" not in s3.list_objects_v2(Bucket="9host-media")


def test_media_rejects_foreign_s3_key(api):
    site_id = create_site(api)
    code, _ = call("POST", f"/api/tenant/sites/{site_id}/media", owner(api), body={"s3_key": "other/x/a.png"})
    assert code == 400


# ---------------------------------------------------------------------------
# Admin/tenant unification
# ---------------------------------------------------------------------------


def test_admin_sites_route_matches_tenant_route(api):
    create_site(api, slug="one")
    create_site(api, slug="two")
    tenant_view = call("GET", "/api/tenant/sites", owner(api))
    admin_view = call("GET", "/api/admin/tenants/acme/sites", superadmin(api), tenant=None)
    assert tenant_view[0] == admin_view[0] == 200
    assert admin_view[1] == tenant_view[1]


def test_admin_tenant_routes_require_superadmin(api):
    assert call("GET", "/api/admin/tenants/acme/sites", owner(api))[0] == 403
    assert call("GET", "/api/admin/tenants/acme/sites", tenant=None)[0] == 401
    code, body = call("GET", "/api/admin/tenants/ghost/sites", superadmin(api), tenant=None)
    assert code == 404 and "Tenant not found" in body["error"]


def test_admin_users_and_tusers_delegate(api):
    sa = superadmin(api)
    code, body = call("POST", "/api/admin/tenants/acme/users", sa, tenant=None,
                      body={"type": "tuser", "username": "jane", "password": "longpassword", "role": "member"})
    assert code == 201 and body["user"]["sub"] == "jane" and body["user"]["type"] == "tuser"
    code, body = call("GET", "/api/admin/tenants/acme/tusers", sa, tenant=None)
    assert code == 200 and [u["username"] for u in body["users"]] == ["jane"]
    assert "password_hash" not in json.dumps(body)
    code, body = call("GET", "/api/admin/tenants/acme/users", sa, tenant=None)
    assert code == 200 and [u["sub"] for u in body["users"]] == ["owner-1"]
    assert call("PUT", "/api/admin/tenants/acme/users/jane/permissions", sa, tenant=None,
                body={"permissions": {"domains": False}})[1]["permissions"]["domains"] is False
    assert call("DELETE", "/api/admin/tenants/acme/users/jane", sa, tenant=None) == (204, None)
    # Member management writes stay superadmin-only on the tenant route.
    assert call("POST", "/api/tenant/users", owner(api), body={"sub": "x"})[0] == 403


def test_admin_settings_put_updates_tier(api, monkeypatch):
    code, body = call("PUT", "/api/admin/tenants/acme/settings", superadmin(api), tenant=None, body={"tier": "BUSINESS"})
    assert code == 200 and body["tier"] == "BUSINESS"


# ---------------------------------------------------------------------------
# Bug #1: default-site route removed; unknown routes 404
# ---------------------------------------------------------------------------


def test_default_site_route_is_gone(api):
    assert call("GET", "/api/tenant/default-site", owner(api))[0] == 404
    assert call("GET", "/api/tenant/default-site")[0] == 404


# ---------------------------------------------------------------------------
# GET /api/admin/edge-kvs
# ---------------------------------------------------------------------------


class FakeKVS:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def list_keys(self, **kwargs):
        self.calls.append(kwargs)
        return self.pages[len(self.calls) - 1]


def test_edge_kvs_superadmin_only_and_hides_internal_keys(api, monkeypatch):
    assert call("GET", "/api/admin/edge-kvs", tenant=None)[0] == 401
    assert call("GET", "/api/admin/edge-kvs", owner(api), tenant=None)[0] == 403

    # KVS not configured -> empty entries, still 200.
    code, body = call("GET", "/api/admin/edge-kvs", superadmin(api), tenant=None)
    assert code == 200 and body == {"entries": [], "domains": []}

    # Rows written after the byEntity backfill marker carry their GSI keys, as register_domain does (T-17).
    api.table.put_item(Item={"pk": "TENANT#acme", "sk": "DOMAIN#myband.com", "site_id": "s1", "status": "ACTIVE",
                             "cf_status": "active", "ssl_status": "active",
                             **entity_keys_domain("acme", "myband.com")})
    api.table.put_item(Item={"pk": "TENANT#zeta", "sk": "DOMAIN#zeta.org", "site_id": "z1",
                             "status": "PENDING_VALIDATION", **entity_keys_domain("zeta", "zeta.org")})
    fake = FakeKVS([
        {"Items": [
            {"Key": "__preview_jwt_secret__", "Value": "super-secret-key"},
            {"Key": "jinks1.echo9.net", "Value": '{"tenant":"acme","site_id":"s1"}'},
        ], "NextToken": "page2"},
        {"Items": [{"Key": "myband.com", "Value": '{"tenant":"acme","site_id":"s1"}'}, {"Key": "__other__", "Value": "x"}]},
    ])
    monkeypatch.setenv("SITE_HOSTS_KVS_ARN", "arn:aws:cloudfront::1:key-value-store/kvs")
    monkeypatch.setattr(site_storage, "_get_kvs_client", lambda: fake)

    code, body = call("GET", "/api/admin/edge-kvs", superadmin(api), tenant=None)
    assert code == 200
    assert body["entries"] == [
        {"hostname": "jinks1.echo9.net", "tenant": "acme", "site_id": "s1"},
        {"hostname": "myband.com", "tenant": "acme", "site_id": "s1"},
    ]
    assert fake.calls[1]["NextToken"] == "page2"
    assert "super-secret-key" not in json.dumps(body) and "__" not in json.dumps(body["entries"])
    assert body["domains"] == [
        {"domain": "myband.com", "tenant_slug": "acme", "site_id": "s1", "status": "ACTIVE",
         "cf_status": "active", "ssl_status": "active"},
        {"domain": "zeta.org", "tenant_slug": "zeta", "site_id": "z1", "status": "PENDING_VALIDATION",
         "cf_status": None, "ssl_status": None},
    ]


# ---------------------------------------------------------------------------
# Bug #8: handler exceptions become a sanitized 500
# ---------------------------------------------------------------------------


def test_handler_exception_returns_sanitized_500(api, monkeypatch, capsys):
    def boom(ctx):
        raise RuntimeError("kaboom secret detail")

    monkeypatch.setattr(handler, "sites_handler", boom)
    code, body = call("GET", "/api/tenant/sites", owner(api))
    assert code == 500
    assert body == {"error": "Internal server error", "request_id": "req-9"}
    assert "kaboom" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# T-12: tenant templates enforce admin/manager for TUSER tokens too
# ---------------------------------------------------------------------------


def test_tuser_template_delete_requires_admin_or_manager(api):
    api.table.put_item(Item={"pk": "TENANT#acme", "sk": "TEMPLATE#mine", "name": "Mine"})
    path = "/api/tenant/templates/mine"
    assert call("DELETE", path, tuser(role="member"))[0] == 403
    assert call("DELETE", path, tuser(role="editor"))[0] == 403
    assert call("PUT", path, tuser(role="member"), body={"name": "X"})[0] == 403
    assert api.table.get_item(Key={"pk": "TENANT#acme", "sk": "TEMPLATE#mine"}).get("Item")
    assert call("DELETE", path, tuser(role="manager"))[0] == 204


# ---------------------------------------------------------------------------
# T-12: draft-preview tokens use a derived key, never the raw TUSER secret
# ---------------------------------------------------------------------------


def test_draft_token_signed_with_derived_key_not_raw_secret(api):
    import hashlib

    site_id = create_site(api)
    code, body = call("GET", f"/api/tenant/sites/{site_id}/draft-token", owner(api))
    assert code == 200, body
    derived = hashlib.sha256(f"{JWT_SECRET}:9host-preview-v1".encode()).hexdigest()
    claims = jwt.decode(body["token"], derived, algorithms=["HS256"])
    assert claims["type"] == "draft" and claims["tenant_slug"] == "acme" and claims["site_id"] == site_id
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(body["token"], JWT_SECRET, algorithms=["HS256"])


def test_users_module_permission_round_trips(api):
    DynamoDBTenantStore(api.table).put_member("acme", {"sub": "jane", "role": "member", "name": "Jane"})
    path = "/api/tenant/users/jane/permissions"
    code, body = call("PUT", path, owner(api), body={"permissions": {"users": False}})
    assert code == 200 and body["permissions"]["users"] is False
    assert call("GET", path, owner(api))[1]["permissions"]["users"] is False


def test_tenant_owner_email_cached_five_minutes(api, monkeypatch):
    import tenant_handler

    tenant_handler._owner_email_cache.clear()
    api.table.put_item(Item={"pk": "TENANT#acme", "sk": "TENANT", "tier": "PRO", "name": "Acme", "owner_sub": "owner-1"})
    calls = []

    class FakeCognito:
        def admin_get_user(self, **kw):
            calls.append(kw["Username"])
            return {"UserAttributes": [{"Name": "email", "Value": "o@acme.test"}]}

    real = tenant_handler.boto3.client
    monkeypatch.setattr(
        tenant_handler.boto3, "client", lambda name, **kw: FakeCognito() if name == "cognito-idp" else real(name, **kw)
    )
    now = [1000.0]
    monkeypatch.setattr(tenant_handler, "_clock", lambda: now[0])
    for _ in range(2):
        code, body = call("GET", "/api/tenant", owner(api))
        assert code == 200 and body["owner_email"] == "o@acme.test"
    assert calls == ["owner-1"]
    now[0] += 301
    call("GET", "/api/tenant", owner(api))
    assert calls == ["owner-1", "owner-1"]
    tenant_handler._owner_email_cache.clear()


# ---------------------------------------------------------------------------
# T-13: legacy-auth handlers migrated to RequestContext
# ---------------------------------------------------------------------------

MANAGER_ONLY_ROUTES = [
    ("POST", "/api/tenant/billing/checkout", {"tier": "pro", "success_url": "https://x/s", "cancel_url": "https://x/c"}),
    ("POST", "/api/tenant/billing/portal", {"return_url": "https://x/r"}),
    ("PATCH", "/api/tenant", {"module_overrides": {"branding": True}}),
    ("PUT", "/api/tenant", {"owner_sub": "owner-1"}),
    ("POST", "/api/tenant/templates/fork", {"template_slug": "basic"}),
    ("PUT", "/api/tenant/templates/mine", {"name": "X"}),
    ("DELETE", "/api/tenant/templates/mine", None),
]


@pytest.mark.parametrize("method,path,body", MANAGER_ONLY_ROUTES)
def test_tuser_member_forbidden_on_manager_routes(api, monkeypatch, method, path, body):
    import billing_handler

    monkeypatch.setenv("BILLING_ENABLED", "true")
    monkeypatch.setattr(billing_handler, "stripe_configured", lambda: True)
    api.table.put_item(Item={"pk": "TENANT#acme", "sk": "TEMPLATE#mine", "name": "Mine"})
    before = api.table.get_item(Key={"pk": "TENANT#acme", "sk": "TENANT"})["Item"]

    code, resp = call(method, path, tuser(role="member"), body=body)
    assert code == 403, resp
    assert set(resp) == {"error"}
    # Nothing was written.
    assert api.table.get_item(Key={"pk": "TENANT#acme", "sk": "TENANT"})["Item"] == before
    assert api.table.get_item(Key={"pk": "TENANT#acme", "sk": "TEMPLATE#mine"}).get("Item")
    # Same for a Cognito member, and for a TUSER token issued for another tenant.
    DynamoDBTenantStore(api.table).put_member("acme", {"sub": "m-1", "role": "member", "name": "M"})
    assert call(method, path, cognito(api.key, "m-1"), body=body)[0] == 403
    assert call(method, path, tuser(role="manager", tenant="other"), body=body)[0] == 403


def test_tuser_manager_passes_role_gate(api):
    code, body = call("PATCH", "/api/tenant", tuser(role="manager"), body={"module_overrides": {"branding": True}})
    assert code == 200 and body["module_overrides"] == {"branding": True}
    code, body = call("PUT", "/api/tenant", tuser(role="manager"), body={"owner_sub": "owner-1"})
    assert code == 403 and "Cognito" in body["error"]  # ownership transfer stays Cognito-owner only


def test_analytics_respects_module_overrides(api):
    code, body = call("GET", "/api/tenant/analytics", tuser(role="member"))
    assert code == 200 and body["placeholder"] is True  # PRO tier, no override

    api.table.update_item(
        Key={"pk": "TENANT#acme", "sk": "TENANT"},
        UpdateExpression="SET module_overrides = :mo",
        ExpressionAttributeValues={":mo": {"advanced_analytics": False}},
    )
    code, body = call("GET", "/api/tenant/analytics", owner(api))
    assert code == 403
    assert body == {
        "error": "Advanced Analytics requires Pro, Business, or VIP tier.",
        "tier": "PRO",
        "upgrade_required": True,
    }

    api.table.put_item(Item={"pk": "TENANT#acme", "sk": "TENANT", "tier": "FREE",
                             "module_overrides": {"advanced_analytics": True}})
    assert call("GET", "/api/tenant/analytics", owner(api))[0] == 200
    assert call("GET", "/api/tenant/analytics")[0] == 401
    assert call("GET", "/api/tenant/analytics", cognito(api.key, "stranger"))[0] == 403


SUPERADMIN_ROUTES = [
    ("GET", "/api/admin/users", None),
    ("GET", "/api/admin/stats", None),
    ("GET", "/api/admin/tenants", None),
    ("POST", "/api/admin/tenants", {"slug": "newco"}),
    ("GET", "/api/admin/tenants/acme", None),
    ("PATCH", "/api/admin/tenants/acme", {"tier": "VIP"}),
    ("GET", "/api/admin/tenants/acme/settings", None),
    ("PUT", "/api/admin/tenants/acme/settings", {"tier": "VIP"}),
    ("DELETE", "/api/admin/tenants/acme", None),
    ("GET", "/api/admin/templates", None),
    ("POST", "/api/admin/templates", {"slug": "tpl"}),
    ("GET", "/api/admin/templates/basic", None),
    ("PUT", "/api/admin/templates/basic", {"name": "X"}),
    ("DELETE", "/api/admin/templates/basic", None),
]


@pytest.mark.parametrize("method,path,body", SUPERADMIN_ROUTES)
def test_superadmin_routes_reject_non_superadmins(api, method, path, body):
    api.table.put_item(Item={"pk": "TENANT#_platform", "sk": "TEMPLATE#basic", "name": "Basic"})
    assert call(method, path, tenant=None, body=body)[0] == 401
    for token in (owner(api), tuser(role="admin")):
        code, resp = call(method, path, token, body=body)
        assert code == 403 and "Superadmin" in resp["error"], (code, resp)
    assert api.table.get_item(Key={"pk": "TENANT#acme", "sk": "TENANT"})["Item"]["tier"] == "PRO"
    assert api.table.get_item(Key={"pk": "TENANT#_platform", "sk": "TEMPLATE#basic"}).get("Item")
    assert not api.table.get_item(Key={"pk": "TENANT#newco", "sk": "TENANT"}).get("Item")


def test_superadmin_routes_use_verified_group_claim(api, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("no Cognito group lookup for a locally verified token")

    monkeypatch.setattr(rc, "_in_superadmin_group", boom)
    code, body = call("GET", "/api/admin/stats", superadmin(api), tenant=None)
    assert code == 200 and body["total_tenants"] == 1
    code, body = call("GET", "/api/admin/tenants", superadmin(api), tenant=None)
    assert code == 200 and [t["slug"] for t in body["tenants"]] == ["acme"]
    code, body = call("GET", "/api/admin/tenants/acme", superadmin(api), tenant=None)
    assert code == 200 and body["tier"] == "PRO"


def test_member_read_routes(api):
    api.table.put_item(Item={"pk": "TENANT#_platform", "sk": "TEMPLATE#basic", "name": "Basic"})
    stranger = cognito(api.key, "stranger")
    for path, query in [("/api/validate-slug", {"slug": "free-slug"}), ("/api/templates", None),
                        ("/api/tenant/templates", None), ("/api/tenant", None)]:
        assert call("GET", path, query=query)[0] == 401
        assert call("GET", path, stranger, query=query)[0] == 403
        assert call("GET", path, tuser(role="member"), query=query)[0] == 200
    assert call("GET", "/api/validate-slug", owner(api), query={"slug": "acme"})[1] == {"available": False, "slug": "acme"}
    assert [t["slug"] for t in call("GET", "/api/templates", owner(api))[1]["templates"]] == ["basic"]
    code, body = call("GET", "/api/tenants", owner(api), tenant=None)
    assert code == 200 and body["tenants"] == [{"slug": "acme", "name": "Acme", "role": "admin"}]
    assert call("GET", "/api/tenants", tuser(), tenant=None)[0] == 401


# ---------------------------------------------------------------------------
# T-18: platform hostnames are reserved as tenant / site slugs
# ---------------------------------------------------------------------------

RESERVED = ["app", "stage", "prod", "www", "tools", "sites-origin", "proxy", "preview", "api", "admin"]


def test_reserved_slug_constant_matches_spec():
    from reserved_slugs import RESERVED_SLUGS

    assert RESERVED_SLUGS == frozenset(RESERVED)


@pytest.mark.parametrize("slug", RESERVED)
def test_validate_slug_reports_reserved_unavailable(api, slug):
    code, body = call("GET", "/api/validate-slug", owner(api), query={"slug": slug.upper()})
    assert code == 200 and body == {"available": False, "slug": slug, "reason": "reserved"}


@pytest.mark.parametrize("slug", RESERVED)
def test_site_create_rejects_reserved_slug(api, slug):
    code, body = call("POST", "/api/tenant/sites", owner(api), body={"name": "X", "slug": slug})
    assert code == 400 and body["code"] == "slug_reserved", body
    assert DynamoDBTenantStore(api.table).list_sites("acme") == []


def test_site_create_rejects_reserved_slug_derived_from_name(api):
    code, body = call("POST", "/api/tenant/sites", owner(api), body={"name": "Admin"})
    assert code == 400 and body["code"] == "slug_reserved"


def test_site_update_rejects_reserved_slug_but_legacy_site_keeps_its_own(api):
    tok = owner(api)
    site_id = create_site(api, slug="band")
    code, body = call("PUT", f"/api/tenant/sites/{site_id}", tok, body={"slug": "app"})
    assert code == 400 and body["code"] == "slug_reserved"
    assert DynamoDBTenantStore(api.table).get_site("acme", site_id)["slug"] == "band"

    # A site created before T-18 with a now-reserved slug can still be edited.
    store = DynamoDBTenantStore(api.table)
    store.put_site("acme", {**store.get_site("acme", site_id), "slug": "tools"})
    code, body = call("PUT", f"/api/tenant/sites/{site_id}", tok, body={"name": "Renamed", "slug": "tools"})
    assert code == 200, body
    code, body = call("GET", "/api/validate-slug", tok, query={"slug": "tools", "exclude_site_id": site_id})
    assert body == {"available": True, "slug": "tools"}
    code, body = call("GET", "/api/validate-slug", tok, query={"slug": "tools"})
    assert body["available"] is False


@pytest.mark.parametrize("slug", ["app", "preview", "sites-origin"])
def test_tenant_create_rejects_reserved_slug(api, slug):
    code, body = call("POST", "/api/tenants", cognito(api.key, "founder-1"), tenant=None, body={"slug": slug})
    assert code == 400 and body["code"] == "slug_reserved", body
    code, body = call("POST", "/api/admin/tenants", superadmin(api), tenant=None, body={"slug": slug})
    assert code == 400 and body["code"] == "slug_reserved", body
    assert api.table.get_item(Key={"pk": f"TENANT#{slug}", "sk": "TENANT"}).get("Item") is None
