"""
T-07: CloudflareSaaSAdapter + custom domain lifecycle (Cloudflare for SaaS + HostMappingKVS).

No network: the adapter runs against FakeCloudflare (an in-memory transport) and the
KVS functions in site_storage are patched.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import cloudflare_saas
import custom_domain_handler
import domains_handler as dh
import secrets_cache
import site_storage
from cloudflare_saas import (
    CNAME_TARGET,
    CloudflareAPIError,
    CloudflareSaaSAdapter,
    InvalidDomainError,
    validate_domain,
)

ZONE = "zone123"
TOKEN = "cf-secret-token-DO-NOT-LOG"
CF_BASE = f"https://api.cloudflare.com/client/v4/zones/{ZONE}/custom_hostnames"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeCloudflare:
    """In-memory Cloudflare Custom Hostnames API exposed as a Transport callable."""

    def __init__(self):
        self.hostnames: dict[str, dict] = {}
        self.calls: list[dict] = []
        self.fail_next: tuple[int, dict] | None = None
        self._n = 0

    def activate(self, hostname_id: str) -> None:
        h = self.hostnames[hostname_id]
        h["status"] = "active"
        h["ssl"]["status"] = "active"
        h.pop("ownership_verification", None)

    def __call__(self, method, url, headers, body):
        payload = json.loads(body) if body else None
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "payload": payload})
        if self.fail_next:
            status, data = self.fail_next
            self.fail_next = None
            return status, json.dumps(data).encode()
        assert url.startswith(CF_BASE), url
        rest = url[len(CF_BASE):].strip("/")
        if method == "POST" and not rest:
            if any(h["hostname"] == payload["hostname"] for h in self.hostnames.values()):
                return 409, json.dumps({"success": False, "errors": [{"code": 1406, "message": "Duplicate custom hostname found."}]}).encode()
            self._n += 1
            hid = f"cfh-{self._n:04d}"
            self.hostnames[hid] = {
                "id": hid,
                "hostname": payload["hostname"],
                "status": "pending",
                "ssl": {"status": "pending_validation", "method": payload["ssl"]["method"], "validation_records": [
                    {"txt_name": f"_acme-challenge.{payload['hostname']}", "txt_value": "ssl-token-abc"}
                ]},
                "ownership_verification": {"type": "txt", "name": f"_cf-custom-hostname.{payload['hostname']}", "value": f"own-{hid}"},
                "verification_errors": ["custom hostname does not CNAME to this zone."],
            }
            return 201, json.dumps({"success": True, "errors": [], "result": self.hostnames[hid]}).encode()
        if rest not in self.hostnames:
            return 404, json.dumps({"success": False, "errors": [{"code": 1436, "message": "The custom hostname was not found."}]}).encode()
        if method == "GET":
            return 200, json.dumps({"success": True, "result": self.hostnames[rest]}).encode()
        if method == "DELETE":
            del self.hostnames[rest]
            return 200, json.dumps({"success": True, "result": {"id": rest}}).encode()
        return 405, b"{}"


@pytest.fixture
def cf(monkeypatch):
    fake = FakeCloudflare()
    custom_domain_handler.set_custom_domain_port(
        CloudflareSaaSAdapter(zone_id=ZONE, api_token=TOKEN, transport=fake)
    )
    yield fake
    custom_domain_handler.set_custom_domain_port(None)


@pytest.fixture
def kvs(monkeypatch):
    store: dict[str, dict] = {}
    calls: list[tuple] = []

    def put_host_mapping(hostname, tenant_slug, site_id):
        calls.append(("put", hostname, tenant_slug, site_id))
        store[hostname] = {"tenant": tenant_slug, "site_id": site_id}
        return True

    def delete_host_mapping(hostname):
        calls.append(("delete", hostname))
        store.pop(hostname, None)
        return True

    monkeypatch.setattr(site_storage, "put_host_mapping", put_host_mapping, raising=False)
    monkeypatch.setattr(site_storage, "delete_host_mapping", delete_host_mapping, raising=False)
    store_calls = type("KVS", (), {"store": store, "calls": calls})
    return store_calls


# Fake auth: token "tok-<tenant>" is a Cognito principal that is admin in <tenant> only.
@pytest.fixture
def auth(monkeypatch):
    import request_context as rc

    def fake_authenticate(event, region=None):
        token = (event.get("headers") or {}).get("authorization", "").replace("Bearer ", "")
        if not token.startswith("tok-"):
            return None
        return rc.Principal(kind="cognito", identifier=f"sub-{token[4:]}", email=None, is_superadmin=False)

    monkeypatch.setattr(rc, "authenticate", fake_authenticate)
    monkeypatch.setattr(rc, "_member_role", lambda table, slug, sub: "admin" if sub == f"sub-{slug}" else None)


def _seed_tenant(table, slug, tier="PRO", site_id="site1"):
    table.put_item(Item={"pk": f"TENANT#{slug}", "sk": "TENANT", "tier": tier, "name": slug})
    table.put_item(Item={"pk": f"TENANT#{slug}", "sk": f"SITE#{site_id}", "entity_type": "SITE", "name": "Site"})


def _event(method, path, tenant, token=None, body=None):
    headers = {"x-tenant-slug": tenant}
    if token is not False:
        headers["authorization"] = f"Bearer {token or 'tok-' + tenant}"
    ev = {"rawPath": path, "requestContext": {"http": {"method": method}}, "headers": headers}
    if body is not None:
        ev["body"] = json.dumps(body)
    return ev


def _call(*args, **kwargs):
    from request_context import run_with_context

    resp = run_with_context(_event(*args, **kwargs), dh.domains_handler)
    body = json.loads(resp["body"]) if resp.get("body") else None
    return resp["statusCode"], body


@pytest.fixture
def env(dynamodb_table, cf, kvs, auth, monkeypatch):
    _seed_tenant(dynamodb_table, "tenanta")
    _seed_tenant(dynamodb_table, "tenantb")
    _seed_tenant(dynamodb_table, "freebie2")
    _seed_tenant(dynamodb_table, "freebie", tier="FREE")
    dns: dict[str, set] = {}  # fake public DNS: TXT name -> values
    monkeypatch.setattr(custom_domain_handler, "txt_values", lambda name: dns.get(name, set()))
    return type("Env", (), {"table": dynamodb_table, "cf": cf, "kvs": kvs, "dns": dns})


def _create_verified(env, domain="myband.com", tenant="tenanta"):
    """Add a domain and publish its _9host-verify TXT (the owner's DNS step)."""
    code, body = _call("POST", "/api/tenant/domains", tenant, body={"domain": domain, "site_id": "site1"})
    assert code == 201, body
    env.dns[f"_9host-verify.{domain}"] = {"unrelated", _row(env.table, tenant, domain)["verify_token"]}
    assert _call("POST", f"/api/tenant/domains/{domain}/activate", tenant)[0] == 200  # verify + register apex/www


def _advance_clock(monkeypatch, seconds):
    """Make domains_handler see ``seconds`` more elapsed time (poll throttle, T-18)."""
    later = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    monkeypatch.setattr(dh, "_utcnow", lambda: later)


def _cf_gets(env):
    return [c for c in env.cf.calls if c["method"] == "GET"]


def _row(table, tenant, domain):
    return table.get_item(Key={"pk": f"TENANT#{tenant}", "sk": f"DOMAIN#{domain}"}).get("Item")


# ---------------------------------------------------------------------------
# Adapter unit tests
# ---------------------------------------------------------------------------


class TestAdapter:
    def test_register_sends_expected_request(self):
        fake = FakeCloudflare()
        rec = CloudflareSaaSAdapter(zone_id=ZONE, api_token=TOKEN, transport=fake).register_hostname("MyBand.com.")
        call = fake.calls[0]
        assert call["method"] == "POST"
        assert call["url"] == CF_BASE
        assert call["headers"]["Authorization"] == f"Bearer {TOKEN}"
        assert call["headers"]["Content-Type"] == "application/json"
        assert call["payload"] == {
            "hostname": "myband.com",
            "ssl": {"method": "http", "type": "dv", "settings": {"min_tls_version": "1.2"}},
        }
        assert rec.cf_hostname_id == "cfh-0001"
        assert rec.domain == "myband.com"
        assert rec.cname_target == CNAME_TARGET == "proxy.echonin9.com"
        assert rec.status == "pending" and rec.ssl_status == "pending_validation"
        assert not rec.is_active
        assert rec.ownership_txt_records == [
            {"type": "TXT", "name": "_cf-custom-hostname.myband.com", "value": "own-cfh-0001", "purpose": "ownership"}
        ]
        assert {"type": "TXT", "name": "_acme-challenge.myband.com", "value": "ssl-token-abc", "purpose": "ssl"} in rec.validation_records
        assert rec.verification_errors == ["custom hostname does not CNAME to this zone."]

    def test_status_and_delete(self):
        fake = FakeCloudflare()
        ad = CloudflareSaaSAdapter(zone_id=ZONE, api_token=TOKEN, transport=fake)
        rec = ad.register_hostname("myband.com")
        fake.activate(rec.cf_hostname_id)
        rec2 = ad.get_hostname_status(rec.cf_hostname_id)
        assert rec2.is_active
        assert fake.calls[-1]["method"] == "GET" and fake.calls[-1]["url"] == f"{CF_BASE}/{rec.cf_hostname_id}"
        ad.delete_hostname(rec.cf_hostname_id)
        assert fake.calls[-1]["method"] == "DELETE"
        assert fake.hostnames == {}
        ad.delete_hostname(rec.cf_hostname_id)  # idempotent on 404

    def test_credentials_from_secret(self, monkeypatch):
        secrets_cache.clear_cache()
        seen = []

        def fake_fetch(secret_id):
            seen.append(secret_id)
            return json.dumps({"zone_id": ZONE, "api_token": TOKEN})

        monkeypatch.setattr(secrets_cache, "_fetch_secret_string", fake_fetch)
        monkeypatch.setenv("CLOUDFLARE_SECRET_ARN", "9host-cloudflare")
        fake = FakeCloudflare()
        CloudflareSaaSAdapter(transport=fake).register_hostname("myband.com")
        assert seen == ["9host-cloudflare"]
        assert fake.calls[0]["url"] == CF_BASE
        secrets_cache.clear_cache()

    def test_missing_secret_is_not_configured(self, monkeypatch):
        secrets_cache.clear_cache()
        monkeypatch.setattr(secrets_cache, "_fetch_secret_string", lambda sid: None)
        fake = FakeCloudflare()
        with pytest.raises(CloudflareAPIError) as ei:
            CloudflareSaaSAdapter(transport=fake).register_hostname("myband.com")
        assert ei.value.http_status == 503 and ei.value.kind == "not_configured"
        assert fake.calls == []

    @pytest.mark.parametrize(
        "status,errors,expected_http,kind",
        [
            (409, [{"code": 1406, "message": "Duplicate custom hostname found."}], 409, "duplicate"),
            (403, [{"code": 10000, "message": "Authentication error"}], 502, "upstream_error"),
            (500, [{"code": 1000, "message": "internal <stack> dump"}], 502, "upstream_error"),
            (400, [{"code": 1411, "message": "hostname invalid"}], 400, "rejected"),
        ],
    )
    def test_api_errors_are_structured_and_safe(self, status, errors, expected_http, kind, caplog):
        fake = FakeCloudflare()
        fake.fail_next = (status, {"success": False, "errors": errors})
        with pytest.raises(CloudflareAPIError) as ei:
            CloudflareSaaSAdapter(zone_id=ZONE, api_token=TOKEN, transport=fake).register_hostname("myband.com")
        err = ei.value
        assert err.http_status == expected_http and err.kind == kind
        body = err.to_response_body()
        assert body["code"] == f"cloudflare_{kind}"
        assert body["cf_error_code"] == errors[0]["code"]
        assert errors[0]["message"] not in json.dumps(body)  # never echo raw CF message to client
        assert TOKEN not in caplog.text

    def test_transport_exception_and_garbage_body(self, caplog):
        def boom(*a):
            raise OSError(f"connection reset {TOKEN}")

        with pytest.raises(CloudflareAPIError) as ei:
            CloudflareSaaSAdapter(zone_id=ZONE, api_token=TOKEN, transport=boom).register_hostname("myband.com")
        assert ei.value.http_status == 502
        assert TOKEN not in caplog.text

        with pytest.raises(CloudflareAPIError):
            CloudflareSaaSAdapter(
                zone_id=ZONE, api_token=TOKEN, transport=lambda *a: (502, b"<html>bad gateway</html>")
            ).get_hostname_status("cfh-1")

    def test_invalid_hostname_id_rejected_without_call(self):
        fake = FakeCloudflare()
        ad = CloudflareSaaSAdapter(zone_id=ZONE, api_token=TOKEN, transport=fake)
        with pytest.raises(CloudflareAPIError):
            ad.get_hostname_status("../../zones")
        assert fake.calls == []

    @pytest.mark.parametrize(
        "bad",
        ["", "localhost", "-bad.com", "bad-.com", "a..b.com", "exa mple.com", "*.example.com",
         "example.123", "foo.echo9.net", "proxy.echonin9.com", "echonin9.com", "echo9.net", "x.echo9.ca", "a" * 64 + ".com",
         "http://example.com", "example.com/path"],
    )
    def test_validate_domain_rejects(self, bad, monkeypatch):
        monkeypatch.setenv("DOMAINS", "echo9.net,echo9.ca")
        with pytest.raises(InvalidDomainError):
            validate_domain(bad)

    @pytest.mark.parametrize("good", ["example.com", "Blog.Example.co.uk", "xn--bcher-kva.example", "my-band.com."])
    def test_validate_domain_accepts(self, good):
        assert validate_domain(good) == good.lower().rstrip(".")

    def test_register_rejects_invalid_domain_without_call(self):
        fake = FakeCloudflare()
        with pytest.raises(InvalidDomainError):
            CloudflareSaaSAdapter(zone_id=ZONE, api_token=TOKEN, transport=fake).register_hostname("not a domain")
        assert fake.calls == []


# ---------------------------------------------------------------------------
# Handler / lifecycle tests
# ---------------------------------------------------------------------------


class TestDomainLifecycle:
    def test_create_writes_pending_row_with_txt_proof_and_no_cloudflare(self, env):
        code, body = _call("POST", "/api/tenant/domains", "tenanta", body={"domain": "MyBand.com", "site_id": "site1"})
        assert code == 201, body
        d = body["domain"]
        assert d["domain"] == "myband.com" and d["www_domain"] == "www.myband.com"
        assert d["status"] == "PENDING_VALIDATION" and d["www_status"] == "PENDING_VALIDATION"
        assert d["cname_target"] == d["verification_cname_target"] == "proxy.echonin9.com"
        row = _row(env.table, "tenanta", "myband.com")
        assert d["validation_records"][0] == {
            "type": "TXT", "name": "_9host-verify.myband.com", "value": row["verify_token"], "purpose": "ownership",
        }
        assert d["acm_validation_records"] == d["validation_records"]
        assert row["verify_token"] in body["message"]
        assert row["gsi2pk"] == "DOMAIN#myband.com" and row["gsi2sk"] == "TENANT#tenanta"
        assert env.cf.calls == [] and env.kvs.calls == []  # nothing provisioned before proof

    def test_www_prefix_is_stripped_to_apex(self, env):
        code, body = _call("POST", "/api/tenant/domains", "tenanta", body={"domain": "www.MyBand.com", "site_id": "site1"})
        assert code == 201 and body["domain"]["domain"] == "myband.com"

    def test_no_txt_no_cloudflare_no_kvs(self, env, monkeypatch):
        _call("POST", "/api/tenant/domains", "tenanta", body={"domain": "myband.com", "site_id": "site1"})
        env.dns["_9host-verify.myband.com"] = {"wrong-token"}
        code, body = _call("POST", "/api/tenant/domains/myband.com/activate", "tenanta")
        assert code == 200 and body["domain"]["status"] == "PENDING_VALIDATION"
        assert env.cf.calls == [] and env.kvs.calls == []

    def test_verified_registers_apex_and_www_then_maps_both(self, env, monkeypatch):
        _create_verified(env)
        code, body = _call("GET", "/api/tenant/domains", "tenanta")  # throttled: activate just polled
        assert code == 200 and body["domains"][0]["status"] == "PENDING_VALIDATION"
        assert [c["payload"]["hostname"] for c in env.cf.calls if c["method"] == "POST"] == ["myband.com", "www.myband.com"]
        row = _row(env.table, "tenanta", "myband.com")
        assert row["cf_hostname_id"] == "cfh-0001" and row["www_cf_hostname_id"] == "cfh-0002"
        assert row["ownership_verified"] is True
        assert env.kvs.calls == []
        assert body["domains"][0]["validation_records"][0]["name"] != "_9host-verify.myband.com"  # proof no longer shown

        env.cf.activate("cfh-0001")
        _advance_clock(monkeypatch, 31)
        code, body = _call("GET", "/api/tenant/domains", "tenanta")
        assert body["domains"][0]["status"] == "ACTIVE" and body["domains"][0]["www_status"] == "PENDING_VALIDATION"
        assert env.kvs.store == {"myband.com": {"tenant": "tenanta", "site_id": "site1"}}

        env.cf.activate("cfh-0002")
        _advance_clock(monkeypatch, 62)
        code, body = _call("GET", "/api/tenant/domains", "tenanta")
        assert body["domains"][0]["www_status"] == "ACTIVE"
        assert env.kvs.store["www.myband.com"] == {"tenant": "tenanta", "site_id": "site1"}

        n = len(env.cf.calls)  # fully ACTIVE rows are not re-polled
        _advance_clock(monkeypatch, 93)
        _call("GET", "/api/tenant/domains", "tenanta")
        _call("GET", "/api/tenant/domains/myband.com", "tenanta")
        assert len(env.cf.calls) == n
        assert _call("POST", "/api/tenant/domains/myband.com/activate", "tenanta")[0] == 400

    def test_dangling_cname_cannot_be_reclaimed_by_another_tenant(self, env):
        """SEC-05: A removes the domain, leaves CNAME + its TXT; B's claim never verifies."""
        _create_verified(env)
        env.cf.activate("cfh-0001")
        env.cf.activate("cfh-0002")
        _call("POST", "/api/tenant/domains/myband.com/activate", "tenanta")
        assert _call("DELETE", "/api/tenant/domains/myband.com", "tenanta")[0] == 204
        assert env.kvs.store == {} and env.cf.hostnames == {}

        assert _call("POST", "/api/tenant/domains", "tenantb", body={"domain": "myband.com", "site_id": "site1"})[0] == 201
        n = len(env.cf.calls)
        code, body = _call("POST", "/api/tenant/domains/myband.com/activate", "tenantb")
        assert code == 200 and body["domain"]["status"] == "PENDING_VALIDATION"
        assert len(env.cf.calls) == n and env.kvs.store == {}

    def test_unverified_claim_does_not_squat(self, env):
        assert _call("POST", "/api/tenant/domains", "tenantb", body={"domain": "myband.com", "site_id": "site1"})[0] == 201
        _create_verified(env)  # the real owner still gets it
        assert len(env.cf.hostnames) == 2
        # ...and once proven, nobody else can add it
        code, body = _call("POST", "/api/tenant/domains", "freebie2", body={"domain": "myband.com", "site_id": "site1"})
        assert code == 409 and "tenanta" not in json.dumps(body)

    def test_status_poll_throttled_per_row(self, env, monkeypatch):
        """T-18: a non-ACTIVE row polled < 30 s ago is not re-checked with Cloudflare."""
        _create_verified(env)
        assert len(env.cf.calls) == 2  # apex + www registered
        for _ in range(3):  # UI polls every 10 s
            _call("GET", "/api/tenant/domains", "tenanta")
            _call("GET", "/api/tenant/domains/myband.com", "tenanta")
        assert len(env.cf.calls) == 2
        _advance_clock(monkeypatch, 31)
        _call("GET", "/api/tenant/domains", "tenanta")
        assert len(_cf_gets(env)) == 2

    def test_failed_poll_keeps_progress(self, env, monkeypatch):
        _create_verified(env)
        env.cf.fail_next = (500, {"success": False, "errors": []})
        _advance_clock(monkeypatch, 31)
        code, body = _call("GET", "/api/tenant/domains", "tenanta")
        assert code == 200 and body["domains"][0]["status"] == "PENDING_VALIDATION"
        row = _row(env.table, "tenanta", "myband.com")
        assert row["ownership_verified"] is True and row["cf_hostname_id"] == "cfh-0001"

    def test_kvs_failure_keeps_domain_pending(self, env, monkeypatch):
        _create_verified(env)
        _call("POST", "/api/tenant/domains/myband.com/activate", "tenanta")
        env.cf.activate("cfh-0001")
        monkeypatch.setattr(site_storage, "put_host_mapping", lambda *a: False, raising=False)
        code, body = _call("POST", "/api/tenant/domains/myband.com/activate", "tenanta")
        assert code == 200 and body["domain"]["status"] == "PENDING_VALIDATION"

    def test_legacy_active_row_is_grandfathered(self, env):
        env.table.put_item(Item={
            "pk": "TENANT#tenanta", "sk": "DOMAIN#legacy.com", "gsi2pk": "DOMAIN#legacy.com",
            "gsi2sk": "TENANT#tenanta", "site_id": "site1", "status": "ACTIVE",
            "acm_certificate_arn": "arn:aws:acm:us-east-1:1:certificate/x",
        })
        code, body = _call("POST", "/api/tenant/domains/legacy.com/activate", "tenanta")
        assert code == 200
        assert body["domain"]["cf_hostname_id"] and body["domain"]["status"] == "PENDING_VALIDATION"
        assert env.cf.calls[-1]["payload"]["hostname"] == "legacy.com"  # no www twin for old rows
        assert _row(env.table, "tenanta", "legacy.com")["ownership_verified"] is True
        assert _call("POST", "/api/tenant/domains", "tenantb", body={"domain": "legacy.com", "site_id": "site1"})[0] == 409

    def test_legacy_pending_row_needs_txt(self, env):
        env.table.put_item(Item={
            "pk": "TENANT#tenanta", "sk": "DOMAIN#old.com", "gsi2pk": "DOMAIN#old.com",
            "gsi2sk": "TENANT#tenanta", "site_id": "site1", "status": "PENDING_VALIDATION", "cf_hostname_id": "cfh-9",
        })
        code, body = _call("POST", "/api/tenant/domains/old.com/activate", "tenanta")
        assert code == 200 and body["domain"]["validation_records"][0]["name"] == "_9host-verify.old.com"
        assert env.cf.calls == []

    def test_delete_removes_both_hostnames_kvs_and_row(self, env):
        _create_verified(env)
        env.cf.fail_next = None
        _call("POST", "/api/tenant/domains/myband.com/activate", "tenanta")
        env.cf.activate("cfh-0001")
        env.cf.activate("cfh-0002")
        _call("POST", "/api/tenant/domains/myband.com/activate", "tenanta")
        assert set(env.kvs.store) == {"myband.com", "www.myband.com"}

        code, body = _call("DELETE", "/api/tenant/domains/myband.com", "tenanta")
        assert code == 204 and body is None
        assert env.cf.hostnames == {} and env.kvs.store == {}
        assert _row(env.table, "tenanta", "myband.com") is None

    def test_delete_cloudflare_error_keeps_row(self, env):
        _create_verified(env)
        _call("POST", "/api/tenant/domains/myband.com/activate", "tenanta")
        env.cf.fail_next = (500, {"success": False, "errors": [{"code": 1000, "message": "boom"}]})
        code, body = _call("DELETE", "/api/tenant/domains/myband.com", "tenanta")
        assert code == 502 and body["code"] == "cloudflare_upstream_error"
        assert "boom" not in json.dumps(body)
        assert _row(env.table, "tenanta", "myband.com") is not None

    def test_activate_surfaces_cloudflare_error(self, env):
        _create_verified(env)
        env.cf.fail_next = (500, {"success": False, "errors": [{"code": 1000, "message": "internal"}]})
        code, body = _call("POST", "/api/tenant/domains/myband.com/activate", "tenanta")
        assert code == 502
        assert body == {"error": "Custom domain provider error. Try again later.", "code": "cloudflare_upstream_error", "cf_error_code": 1000}
        assert _row(env.table, "tenanta", "myband.com")["ownership_verified"] is True

    @pytest.mark.parametrize("domain", ["not a domain", "shop.echo9.net", "*.example.com", "www.echo9.net"])
    def test_invalid_domain_rejected(self, env, domain):
        code, body = _call("POST", "/api/tenant/domains", "tenanta", body={"domain": domain, "site_id": "site1"})
        assert code == 400 and "error" in body
        assert env.cf.calls == []

    def test_missing_fields_and_unknown_site(self, env):
        assert _call("POST", "/api/tenant/domains", "tenanta", body={"site_id": "site1"})[0] == 400
        assert _call("POST", "/api/tenant/domains", "tenanta", body={"domain": "a.com"})[0] == 400
        assert _call("POST", "/api/tenant/domains", "tenanta", body={"domain": "a.com", "site_id": "nope"})[0] == 404
        assert env.cf.calls == []

    def test_duplicate_domain_same_and_other_tenant(self, env):
        _create_verified(env)
        assert _call("POST", "/api/tenant/domains", "tenanta", body={"domain": "myband.com", "site_id": "site1"})[0] == 409
        for d in ("myband.com", "www.myband.com"):
            code, body = _call("POST", "/api/tenant/domains", "tenantb", body={"domain": d, "site_id": "site1"})
            assert code == 409 and "tenanta" not in json.dumps(body)

    def test_tier_gating(self, env):
        code, body = _call("POST", "/api/tenant/domains", "freebie", body={"domain": "free.com", "site_id": "site1"})
        assert code == 403 and body["upgrade_required"] is True
        assert _call("GET", "/api/tenant/domains", "freebie")[0] == 403
        assert env.cf.calls == []

    def test_tenant_isolation(self, env):
        _call("POST", "/api/tenant/domains", "tenantb", body={"domain": "bband.com", "site_id": "site1"})
        cf_calls = len(env.cf.calls)

        # tenant A cannot see, refresh or delete tenant B's domain via its own tenant scope
        code, body = _call("GET", "/api/tenant/domains", "tenanta")
        assert code == 200 and body["domains"] == []
        assert _call("GET", "/api/tenant/domains/bband.com", "tenanta")[0] == 404
        assert _call("POST", "/api/tenant/domains/bband.com/activate", "tenanta")[0] == 404
        assert _call("DELETE", "/api/tenant/domains/bband.com", "tenanta")[0] == 404

        # nor by pointing X-Tenant-Slug at tenant B with tenant A's credentials
        assert _call("DELETE", "/api/tenant/domains/bband.com", "tenantb", token="tok-tenanta")[0] == 403
        assert _call("GET", "/api/tenant/domains", "tenantb", token="tok-tenanta")[0] == 403

        assert len(env.cf.calls) == cf_calls
        assert env.kvs.calls == []
        assert _row(env.table, "tenantb", "bband.com") is not None

    def test_unauthenticated(self, env):
        assert _call("GET", "/api/tenant/domains", "tenanta", token=False)[0] == 401


class TestDeletionFailures:
    """SEC-21: a failed Cloudflare/KVS delete keeps the row so a retry can finish."""

    def test_kvs_delete_failure_keeps_row_then_retry_succeeds(self, env, monkeypatch):
        _create_verified(env)
        monkeypatch.setattr(site_storage, "delete_host_mapping", lambda h: False, raising=False)
        code, body = _call("DELETE", "/api/tenant/domains/myband.com", "tenanta")
        assert code == 502 and _row(env.table, "tenanta", "myband.com") is not None
        monkeypatch.setattr(site_storage, "delete_host_mapping", lambda h: True, raising=False)
        assert _call("DELETE", "/api/tenant/domains/myband.com", "tenanta")[0] == 204  # CF delete idempotent
        assert _row(env.table, "tenanta", "myband.com") is None
