#!/usr/bin/env python3
"""Read-only blocks rollout check (T-31f step 6).

Compiles one site locally in live mode twice -- as stored (control) and with
site.editor forced to "blocks" -- and diffs both against a downloaded copy of
its published/current/ bundle. Writes nothing to DynamoDB or S3.

Pass: control == before (proves the harness), and blocks differs only in style.css,
by an appended suffix.

Usage:
  aws s3 sync s3://9host-sites/<tenant>/<site_id>/published/current/ <before_dir>
  CLOUDFRONT_MEDIA_URL=... DOMAINS=... python scripts/compare_blocks_output.py \
      --table 9host-main --tenant jinks --site <site_id> --before <before_dir>
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

import boto3

from publish_handler import _build_snapshot, _compile_inputs
from site_compiler import compile_site
from tenant_store import DynamoDBTenantStore


def _diff(before: dict[str, bytes], after: dict[str, bytes]) -> list[str]:
    return sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--table", required=True)
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--site", required=True)
    ap.add_argument("--before", required=True, help="local copy of published/current/")
    a = ap.parse_args()

    table = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1")).Table(a.table)
    store = DynamoDBTenantStore(table)
    site = store.get_site(a.tenant, a.site)
    if not site:
        print("site not found")
        return 2
    root = Path(a.before)
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def build(editor_site: dict) -> dict[str, bytes]:
        template, features, media_base = _compile_inputs(store, a.tenant, editor_site)
        snap = _build_snapshot(table, a.tenant, a.site, editor_site, template, media_base, features,
                               published_only=True, generated_at=site.get("published_at") or "")
        return compile_site(snap, mode="live").files

    control = build(dict(site))
    blocks = build({**site, "editor": "blocks"})
    c_diff, b_diff = _diff(before, control), _diff(before, blocks)
    print(f"editor(stored)={site.get('editor')!r} files before={len(before)} control={len(control)} blocks={len(blocks)}")
    print(f"control vs before: {c_diff or 'identical'}")
    print(f"blocks  vs before: {b_diff or 'identical'}")
    css_ok = b_diff == ["style.css"] and blocks["style.css"].startswith(before["style.css"])
    if css_ok:
        print(f"style.css: appended {len(blocks['style.css']) - len(before['style.css'])} bytes")
    ok = not c_diff and css_ok
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
