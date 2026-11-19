#!/usr/bin/env python3
"""
Re-publish all published sites (Task 1.8).

Finds all sites with status=published and a template_id, then
re-publishes each by invoking the publish handler's core logic directly.
This picks up any template CSS/HTML rendering changes.

Dry run by default (SEC-29); --apply publishes. Inputs come from publish_handler._compile_inputs,
exactly like the API (tenant tier features, pinned template tokens, SITE_META-aware site row).

Usage:
  python scripts/republish_all_sites.py --table 9host-main                      # list only
  python scripts/republish_all_sites.py --table 9host-main --tenant my-tenant --apply
"""

import argparse
import json
import os
import sys

# Allow importing api modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

import boto3

from dynamodb_helpers import pk_tenant


def _find_published_sites(table, tenant_slug: str | None = None):
    """Scan/query for sites with status=published and a template_id."""
    sites = []

    if tenant_slug:
        # Query specific tenant
        resp = table.query(
            KeyConditionExpression="pk = :pk AND begins_with(sk, :sk_prefix)",
            ExpressionAttributeValues={
                ":pk": pk_tenant(tenant_slug),
                ":sk_prefix": "SITE#",
            },
        )
        items = resp.get("Items", [])
    else:
        # Scan all tenants
        items = []
        params = {
            "FilterExpression": "begins_with(sk, :sk_prefix)",
            "ExpressionAttributeValues": {":sk_prefix": "SITE#"},
        }
        while True:
            resp = table.scan(**params)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            params["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    for item in items:
        # Only include actual site records (not PAGE/POST/EVENT/MEDIA sub-items)
        sk = item.get("sk", "")
        if sk.count("#") != 1:
            continue
        status = (item.get("status") or "").lower()
        template_id = (item.get("template_id") or "").strip()
        if status == "published" and template_id:
            t_slug = item["pk"].replace("TENANT#", "")
            site_id = sk.replace("SITE#", "")
            sites.append({
                "tenant_slug": t_slug,
                "site_id": site_id,
                "name": item.get("name", ""),
                "template_id": template_id,
                "slug": item.get("slug", ""),
            })

    return sites


def republish(table_name: str, region: str, tenant_slug: str | None, dry_run: bool):
    from publish_handler import _compile_inputs, _publish_site
    from tenant_store import DynamoDBTenantStore

    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)
    store = DynamoDBTenantStore(table)
    s3_client = boto3.client("s3", region_name=region)

    sites = _find_published_sites(table, tenant_slug)
    if not sites:
        print("No published sites found.")
        return

    print(f"Found {len(sites)} published site(s) to re-publish:\n")
    for s in sites:
        print(f"  [{s['tenant_slug']}] {s['name']} ({s['site_id']}) — template: {s['template_id']}")

    if dry_run:
        print("\nDry run: no changes made. Re-run with --apply to publish.")
        return

    print()
    success = 0
    failed = 0

    for s in sites:
        tenant = s["tenant_slug"]
        site_id = s["site_id"]
        label = f"[{tenant}] {s['name']}"

        site_item = store.get_site(tenant, site_id)
        if not site_item:
            print(f"  SKIP {label} — site record not found")
            failed += 1
            continue

        try:
            template_item, features, media_base = _compile_inputs(store, tenant, site_item)
            result = _publish_site(
                table, s3_client, tenant, site_id, site_item, template_item, media_base, resolved_features=features
            )
            v = result.get("version", "?")
            fc = result.get("files_count", "?")
            print(f"  OK   {label} — v{v}, {fc} files")
            success += 1
        except Exception as e:
            print(f"  FAIL {label} — {e}")
            failed += 1

    print(f"\nDone. {success} succeeded, {failed} failed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-publish all published sites")
    parser.add_argument("--table", default=os.environ.get("DYNAMODB_TABLE", "9host-main"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--tenant", default=None, help="Limit to a specific tenant slug")
    parser.add_argument("--apply", action="store_true", help="Actually publish (default: list only)")
    args = parser.parse_args()

    republish(args.table, args.region, args.tenant, not args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
