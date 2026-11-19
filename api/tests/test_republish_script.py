"""SEC-29: republish_all_sites.py is a dry run by default and publishes with the API's inputs."""
import importlib.util
import pathlib

import publish_handler
from tenant_store import DynamoDBTenantStore

_spec = importlib.util.spec_from_file_location(
    "republish_all_sites", pathlib.Path(__file__).resolve().parents[2] / "scripts" / "republish_all_sites.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_dry_run_default_and_apply_uses_compile_inputs(dynamodb_table, monkeypatch):
    store = DynamoDBTenantStore(dynamodb_table)
    store.put_tenant("acme", {"tier": "FREE"})
    site = store.put_site("acme", {"name": "S", "slug": "s", "status": "published", "template_id": "t1"})
    published = []
    monkeypatch.setattr(publish_handler, "_compile_inputs", lambda st, t, s: ({"slug": "t1"}, {"media_gallery": False}, "/media/"))
    monkeypatch.setattr(publish_handler, "_publish_site", lambda *a, **k: published.append(k) or {"version": 1})
    monkeypatch.setattr(mod.boto3, "resource", lambda *a, **k: type("R", (), {"Table": lambda self, n: dynamodb_table})())

    mod.republish("9host-main", "us-east-1", "acme", dry_run=True)
    assert published == []
    mod.republish("9host-main", "us-east-1", "acme", dry_run=False)
    assert published == [{"resolved_features": {"media_gallery": False}}]
    assert site["id"]
