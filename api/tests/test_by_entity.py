"""
T-17: tenant and custom-domain rows are indexed in the byEntity GSI (gsi3pk ENTITY#TENANT /
ENTITY#DOMAIN) so the superadmin lists are GSI Queries instead of full-table Scans.

Covers: keys written at create/update time, pre-T-17 rows (no gsi3 keys) still listed via the
one-off backfill (lazy on first read, or scripts/backfill_by_entity.py), and no Scan on the three
superadmin paths (GET /api/admin/tenants, /api/admin/stats, /api/admin/edge-kvs) once backfilled.
"""

import importlib.util
import os

import botocore.client
import pytest

import custom_domain_handler
from cloudflare_saas import CloudflareSaaSAdapter
from tenant_store import (
    BY_ENTITY_MIGRATION_SK,
    ENTITY_DOMAIN,
    ENTITY_TENANT,
    DynamoDBTenantStore,
    InMemoryTenantStore,
    entity_keys_domain,
    entity_keys_tenant,
)
from tests.test_cloudflare_saas import ZONE, TOKEN, FakeCloudflare
from tests.test_handlers_integration import api, call, rsa_key, superadmin  # noqa: F401 (fixtures)

MARKER = ("TENANT#_platform", BY_ENTITY_MIGRATION_SK)


@pytest.fixture
def api_ops(monkeypatch):
    """Record every DynamoDB API operation name (moto still serves them)."""
    ops: list[str] = []
    real = botocore.client.BaseClient._make_api_call

    def spy(self, operation_name, api_params):
        ops.append(operation_name)
        return real(self, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", spy)
    return ops


def _legacy_rows():
    """Pre-T-17 rows: no gsi3 keys."""
    return [
        {"pk": "TENANT#acme", "sk": "TENANT", "name": "Acme", "tier": "PRO"},
        {"pk": "TENANT#zeta", "sk": "TENANT", "name": "Zeta"},
        {"pk": "TENANT#acme", "sk": "DOMAIN#myband.com", "site_id": "s1", "status": "ACTIVE"},
        {"pk": "TENANT#acme", "sk": "SITE#s1", "slug": "band"},  # not a tenant/domain row
    ]


@pytest.fixture(params=["memory", "dynamodb"])
def store(request):
    if request.param == "memory":
        s = InMemoryTenantStore()
        for row in _legacy_rows():
            s._put(row)
        return s
    table = request.getfixturevalue("dynamodb_table")
    for row in _legacy_rows():
        table.put_item(Item=row)
    return DynamoDBTenantStore(table)


def _raw(store, pk, sk):
    return store._get(pk, sk)


# ---------------------------------------------------------------------------
# TenantStore (both backends)
# ---------------------------------------------------------------------------


def test_preexisting_rows_still_listed_and_backfilled(store):
    tenants = store.list_all_tenants()
    assert [t["slug"] for t in tenants] == ["acme", "zeta"]
    assert tenants[0]["name"] == "Acme" and "gsi3pk" not in tenants[0] and "pk" not in tenants[0]
    domains = store.list_all_domains()
    assert [(d["pk"], d["sk"]) for d in domains] == [("TENANT#acme", "DOMAIN#myband.com")]

    assert _raw(store, "TENANT#acme", "TENANT")["gsi3pk"] == ENTITY_TENANT
    assert _raw(store, "TENANT#acme", "DOMAIN#myband.com")["gsi3sk"] == "TENANT#acme#DOMAIN#myband.com"
    assert "gsi3pk" not in _raw(store, "TENANT#acme", "SITE#s1")
    assert _raw(store, *MARKER) is not None


def test_backfill_is_idempotent_and_dry_run_writes_nothing(store):
    assert store.backfill_by_entity(dry_run=True) == {"tenants": 2, "domains": 1}
    assert _raw(store, *MARKER) is None
    assert "gsi3pk" not in _raw(store, "TENANT#zeta", "TENANT")
    assert store.backfill_by_entity() == {"tenants": 2, "domains": 1}
    assert store.backfill_by_entity() == {"tenants": 0, "domains": 0}
    assert _raw(store, *MARKER) is not None


def test_put_and_update_tenant_write_entity_keys(store):
    store.backfill_by_entity()
    out = store.put_tenant("newco", {"name": "NewCo", "slug": "ignored", "gsi3pk": "bogus"})
    assert out == {"name": "NewCo", "slug": "newco"}
    assert {k: _raw(store, "TENANT#newco", "TENANT")[k] for k in ("gsi3pk", "gsi3sk")} == entity_keys_tenant("newco")
    assert [t["slug"] for t in store.list_all_tenants()] == ["acme", "newco", "zeta"]

    # update_tenant self-heals a row that lost its index entry.
    store._put({"pk": "TENANT#orphan", "sk": "TENANT", "name": "Orphan"})
    assert "orphan" not in [t["slug"] for t in store.list_all_tenants()]
    store.update_tenant("orphan", {"tier": "VIP"})
    assert "orphan" in [t["slug"] for t in store.list_all_tenants()]


def test_deleted_tenant_and_domains_leave_the_index(store):
    store.backfill_by_entity()
    store.delete_tenant_cascade("acme")
    assert [t["slug"] for t in store.list_all_tenants()] == ["zeta"]
    assert store.list_all_domains() == []


def test_dynamodb_lists_query_by_entity_without_scan_after_backfill(dynamodb_table, api_ops):
    for row in _legacy_rows():
        dynamodb_table.put_item(Item=row)
    store = DynamoDBTenantStore(dynamodb_table)
    store.list_all_tenants()  # first read backfills (one Scan)
    assert api_ops.count("Scan") == 1
    api_ops.clear()
    assert [t["slug"] for t in store.list_all_tenants()] == ["acme", "zeta"]
    assert len(store.list_all_domains()) == 1
    assert "Scan" not in api_ops and "Query" in api_ops


def test_register_domain_writes_entity_keys(dynamodb_table):
    fake = FakeCloudflare()
    custom_domain_handler.set_custom_domain_port(CloudflareSaaSAdapter(zone_id=ZONE, api_token=TOKEN, transport=fake))
    try:
        item = custom_domain_handler.register_domain(dynamodb_table, "acme", "myband.com", "s1")
    finally:
        custom_domain_handler.set_custom_domain_port(None)
    assert {k: item[k] for k in ("gsi3pk", "gsi3sk")} == entity_keys_domain("acme", "myband.com")
    store = DynamoDBTenantStore(dynamodb_table)
    store.backfill_by_entity()
    assert [d["sk"] for d in store.list_all_domains()] == ["DOMAIN#myband.com"]
    assert store.list_all_domains()[0]["gsi3pk"] == ENTITY_DOMAIN


# ---------------------------------------------------------------------------
# Handlers: the three superadmin paths
# ---------------------------------------------------------------------------


def test_superadmin_paths_list_legacy_rows_then_never_scan(api, api_ops):  # noqa: F811
    # 'acme' (fixture) has no gsi3 keys; add another legacy tenant and a legacy domain row.
    api.table.put_item(Item={"pk": "TENANT#zeta", "sk": "TENANT", "name": "Zeta", "tier": "FREE"})
    api.table.put_item(Item={"pk": "TENANT#zeta", "sk": "DOMAIN#zeta.org", "site_id": "z1", "status": "ACTIVE"})
    sa = superadmin(api)

    code, body = call("GET", "/api/admin/tenants", sa, tenant=None)
    assert code == 200 and [t["slug"] for t in body["tenants"]] == ["acme", "zeta"]
    assert api_ops.count("Scan") == 1  # one-off lazy backfill

    api_ops.clear()
    code, body = call("POST", "/api/admin/tenants", sa, tenant=None, body={"slug": "newco"})
    assert code == 201
    code, body = call("GET", "/api/admin/tenants", sa, tenant=None)
    assert [t["slug"] for t in body["tenants"]] == ["acme", "newco", "zeta"]
    code, body = call("GET", "/api/admin/stats", sa, tenant=None)
    assert code == 200 and body["total_tenants"] == 3
    code, body = call("GET", "/api/admin/edge-kvs", sa, tenant=None)
    assert code == 200 and [d["domain"] for d in body["domains"]] == ["zeta.org"]
    assert "Scan" not in api_ops


def test_admin_patch_tenant_self_heals_index(api):  # noqa: F811
    store = DynamoDBTenantStore(api.table)
    store.backfill_by_entity()
    api.table.put_item(Item={"pk": "TENANT#late", "sk": "TENANT", "name": "Late"})  # unindexed
    code, _ = call("PATCH", "/api/admin/tenants/late", superadmin(api), tenant=None, body={"tier": "PRO"})
    assert code == 200
    assert "late" in [t["slug"] for t in store.list_all_tenants()]


# ---------------------------------------------------------------------------
# scripts/backfill_by_entity.py
# ---------------------------------------------------------------------------


def _load_script():
    path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "backfill_by_entity.py")
    spec = importlib.util.spec_from_file_location("backfill_by_entity", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_backfill_script_dry_run_then_apply(dynamodb_table, capsys):
    for row in _legacy_rows():
        dynamodb_table.put_item(Item=row)
    script = _load_script()
    assert script.main(["--table", dynamodb_table.name, "--dry-run"]) == 0
    assert "Would index 2 tenant row(s) and 1 domain row(s)" in capsys.readouterr().out
    assert "Item" not in dynamodb_table.get_item(Key={"pk": MARKER[0], "sk": MARKER[1]})

    assert script.main(["--table", dynamodb_table.name]) == 0
    assert "Indexed 2 tenant row(s) and 1 domain row(s)" in capsys.readouterr().out
    assert script.main(["--table", dynamodb_table.name]) == 0
    assert "Indexed 0 tenant row(s) and 0 domain row(s)" in capsys.readouterr().out
