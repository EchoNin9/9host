#!/usr/bin/env python3
"""
Backfill `doc` on legacy PAGE items (T-31f, ADR-0003 §4).

Every PAGE item (sk=SITE#{site_id}#PAGE#{path}) without a `doc` gets
doc = compact JSON of legacy_doc(body) -- the exact form content_handler saves. `_home` pages
are skipped, `body` and every other attribute are left alone. Writes are conditional
(attribute_not_exists(doc)), so the script is idempotent and never overwrites an editor save.

Dry run is the default; pass --apply to write.

Usage:
  python scripts/backfill_page_docs.py --table 9host-main
  python scripts/backfill_page_docs.py --table 9host-main --tenant jinks --site <site_id>
  python scripts/backfill_page_docs.py --table 9host-main --apply
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Allow importing api modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from blocks import legacy_doc
from reserved_slugs import HOME_PAGE_PATH


def dump_doc(doc: dict) -> str:
    """Same serialization as content_handler._apply_doc."""
    return json.dumps(doc, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def _pages(table, tenant: str | None, site: str | None):
    """Yield PAGE items, querying one tenant partition when --tenant is given."""
    if tenant:
        prefix = f"SITE#{site}#PAGE#" if site else "SITE#"
        kwargs = {"KeyConditionExpression": Key("pk").eq(f"TENANT#{tenant}") & Key("sk").begins_with(prefix)}
        op = table.query
    else:
        kwargs = {"FilterExpression": Attr("pk").begins_with("TENANT#") & Attr("sk").contains("#PAGE#")}
        op = table.scan
    while True:
        resp = op(**kwargs)
        for item in resp.get("Items", []):
            sk = item.get("sk", "")
            if not sk.startswith("SITE#") or "#PAGE#" not in sk:
                continue
            site_id, path = sk[len("SITE#"):].split("#PAGE#", 1)
            if site and site_id != site:
                continue
            yield item, item["pk"][len("TENANT#"):], site_id, path
        if "LastEvaluatedKey" not in resp:
            return
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def backfill(table, tenant: str | None = None, site: str | None = None, apply: bool = False) -> Counter:
    counts: Counter = Counter()
    per_site: Counter = Counter()
    for item, t, s, path in _pages(table, tenant, site):
        counts["scanned"] += 1
        if "doc" in item:
            action = "has-doc"
        elif path == HOME_PAGE_PATH:
            action = "skip-home"
        elif not apply:
            action = "pending"
        else:
            try:
                table.update_item(
                    Key={"pk": item["pk"], "sk": item["sk"]},
                    UpdateExpression="SET #doc = :doc",
                    ConditionExpression="attribute_exists(pk) AND attribute_not_exists(#doc)",
                    ExpressionAttributeNames={"#doc": "doc"},
                    ExpressionAttributeValues={":doc": dump_doc(legacy_doc(item.get("body", "")))},
                )
                action = "written"
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                    raise
                action = "skip-raced"
        counts[action] += 1
        if action in ("pending", "written"):
            per_site[(t, s)] += 1
        print(f"{t}\t{s}\t{path}\t{action}")

    mode = "APPLY" if apply else "DRY RUN"
    print(f"--- {mode}: scanned={counts['scanned']} has-doc={counts['has-doc']} "
          f"skip-home={counts['skip-home']} pending={counts['pending']} written={counts['written']} "
          f"skip-raced={counts['skip-raced']}")
    for (t, s), n in sorted(per_site.items()):
        print(f"  {t}\t{s}\t{'written' if apply else 'pending'}={n}")
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Backfill legacy `doc` on PAGE items (dry run by default)")
    parser.add_argument("--table", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="default; report only")
    mode.add_argument("--apply", action="store_true", help="write the docs")
    parser.add_argument("--tenant", help="tenant slug filter")
    parser.add_argument("--site", help="site_id filter")
    args = parser.parse_args(argv)

    backfill(boto3.resource("dynamodb").Table(args.table), args.tenant, args.site, apply=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
