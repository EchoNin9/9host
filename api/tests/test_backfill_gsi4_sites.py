"""SEC-14: the CI gsi4 backfill must index sites only, never blog posts or other child rows."""
import importlib.util
import pathlib

from tests.test_handlers_integration import api, call, cognito, create_site, owner, rsa_key  # noqa: F401
from tenant_store import DynamoDBTenantStore

_spec = importlib.util.spec_from_file_location(
    "backfill_gsi4_sites", pathlib.Path(__file__).resolve().parents[2] / "scripts" / "backfill_gsi4_sites.py")
backfill_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backfill_mod)


def test_backfill_skips_post_rows(api):
    site_id = create_site(api, slug="attacker-site")
    assert call("POST", f"/api/tenant/sites/{site_id}/posts", owner(api),
                body={"slug": "victim-brand", "title": "x"})[0] in (200, 201)
    backfill_mod.backfill("9host-main", dry_run=False)
    assert DynamoDBTenantStore(api.table).resolve_site_slug("victim-brand") is None
    assert call("POST", "/api/tenants", cognito(api.key, "founder-1"), tenant=None, body={"slug": "victim-brand"})[0] == 201


def test_polluted_rows_ignored_then_cleaned(api):
    store = DynamoDBTenantStore(api.table)
    store.put_site("acme", {"id": "s1", "name": "A", "slug": "a1", "status": "draft"})
    store.put_content("acme", "s1", "POST", {"slug": "news", "title": "t"})
    post = [i for i in api.table.scan()["Items"] if "#POST#" in i["sk"]][0]
    api.table.update_item(Key={"pk": post["pk"], "sk": post["sk"]}, UpdateExpression="SET gsi4pk = :p, gsi4sk = :s",
                          ExpressionAttributeValues={":p": "SLUG#news", ":s": post["sk"]})  # what the old script did
    assert store.resolve_site_slug("news") is None  # ignored at read time
    assert backfill_mod.cleanup_child_rows("9host-main", apply=False) == 1
    assert "gsi4pk" in api.table.get_item(Key={"pk": post["pk"], "sk": post["sk"]})["Item"]  # dry run wrote nothing
    backfill_mod.cleanup_child_rows("9host-main", apply=True)
    assert "gsi4pk" not in api.table.get_item(Key={"pk": post["pk"], "sk": post["sk"]})["Item"]
    assert store.resolve_site_slug("a1")["site_id"] == "s1"
