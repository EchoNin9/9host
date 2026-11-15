"""scripts/backfill_page_docs.py (T-31f): legacy `doc` backfill on PAGE items, against moto."""

import importlib.util
import inspect
import json
import os

import pytest

import content_handler
from blocks import legacy_doc

SITE = "s1"
OTHER_SITE = "s2"


def _load_script():
    path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "backfill_page_docs.py")
    spec = importlib.util.spec_from_file_location("backfill_page_docs", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _expected(body: str) -> str:
    # The form content_handler._apply_doc stores.
    return json.dumps(legacy_doc(body), separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def _page(tenant, site, path, **attrs):
    return {"pk": f"TENANT#{tenant}", "sk": f"SITE#{site}#PAGE#{path}", "path": path, **attrs}


ROWS = [
    _page("acme", SITE, "about", title="About", body="<p>Café — ünïcode</p>", status="PUBLISHED"),
    _page("acme", SITE, "contact", title="Contact", body="<p>Mail us</p>"),
    _page("acme", SITE, "nobody", title="No body"),
    _page("acme", SITE, "edited", body="<p>new</p>", doc='{"keep":"me"}'),
    _page("acme", SITE, "_home", body="<p>home</p>"),
    _page("acme", OTHER_SITE, "about", body="<p>other site</p>"),
    _page("zeta", SITE, "about", body="<p>zeta</p>"),
    {"pk": "TENANT#acme", "sk": f"SITE#{SITE}", "name": "Site"},
    {"pk": "TENANT#acme", "sk": f"SITE#{SITE}#POST#hello", "body": "<p>post</p>"},
]


@pytest.fixture
def table(dynamodb_table):
    for row in ROWS:
        dynamodb_table.put_item(Item=row)
    return dynamodb_table


def _snapshot(table):
    return {(i["pk"], i["sk"]): i for i in table.scan()["Items"]}


def _run(script, table, *args):
    return script.main(["--table", table.name, *args])


def test_serialization_matches_content_handler():
    src = inspect.getsource(content_handler._apply_doc)
    assert 'json.dumps(doc, separators=(",", ":"), ensure_ascii=False, sort_keys=True)' in src
    assert _load_script().dump_doc(legacy_doc("<p>é</p>")) == _expected("<p>é</p>")


def test_dry_run_is_default_and_writes_nothing(table, capsys):
    before = _snapshot(table)
    assert _run(_load_script(), table) == 0
    out = capsys.readouterr().out
    assert _snapshot(table) == before
    assert "acme\ts1\tcontact\tpending" in out
    assert "acme\ts1\tedited\thas-doc" in out
    assert "acme\ts1\t_home\tskip-home" in out
    assert "--- DRY RUN: scanned=7 has-doc=1 skip-home=1 pending=5 written=0" in out
    assert "  acme\ts1\tpending=3" in out
    # --dry-run is accepted explicitly too
    assert _run(_load_script(), table, "--dry-run") == 0
    assert _snapshot(table) == before


def test_apply_writes_legacy_docs_then_is_idempotent(table, capsys):
    script = _load_script()
    before = _snapshot(table)
    assert _run(script, table, "--apply") == 0
    assert "--- APPLY: scanned=7 has-doc=1 skip-home=1 pending=0 written=5" in capsys.readouterr().out
    after = _snapshot(table)

    for key, row in before.items():
        new = dict(after[key])
        is_target = "#PAGE#" in key[1] and "doc" not in row and not key[1].endswith("#_home")
        if is_target:
            assert new.pop("doc") == _expected(row.get("body", ""))
        assert new == row  # body and every other attribute untouched; non-targets fully untouched

    assert _run(script, table, "--apply") == 0
    out = capsys.readouterr().out
    assert "written=0" in out and "has-doc=6" in out
    assert _snapshot(table) == after


def test_tenant_and_site_filters(table, capsys):
    script = _load_script()
    before = _snapshot(table)
    assert _run(script, table, "--apply", "--tenant", "acme", "--site", SITE) == 0
    assert "written=3" in capsys.readouterr().out
    after = _snapshot(table)
    assert "doc" not in after[("TENANT#acme", f"SITE#{OTHER_SITE}#PAGE#about")]
    assert after[("TENANT#zeta", f"SITE#{SITE}#PAGE#about")] == before[("TENANT#zeta", f"SITE#{SITE}#PAGE#about")]

    assert _run(script, table, "--apply", "--tenant", "acme") == 0
    assert "written=1" in capsys.readouterr().out
    assert "doc" not in _snapshot(table)[("TENANT#zeta", f"SITE#{SITE}#PAGE#about")]


def test_conditional_write_skips_a_doc_saved_mid_run(table, capsys):
    script = _load_script()
    real_update = table.update_item
    key = {"pk": "TENANT#acme", "sk": f"SITE#{SITE}#PAGE#contact"}

    def racing_update(**kw):
        if kw["Key"] == key:  # an editor save lands between the scan and our write
            table.update_item = real_update
            real_update(Key=key, UpdateExpression="SET #d = :d",
                        ExpressionAttributeNames={"#d": "doc"}, ExpressionAttributeValues={":d": "saved"})
            table.update_item = racing_update
        return real_update(**kw)

    table.update_item = racing_update
    script.backfill(table, apply=True)
    assert "acme\ts1\tcontact\tskip-raced" in capsys.readouterr().out
    assert table.get_item(Key=key)["Item"]["doc"] == "saved"
