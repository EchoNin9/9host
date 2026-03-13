#!/usr/bin/env python3
"""
Backfill gsi4pk/gsi4sk on existing SITE items (Task 1.76).

Required for GSI bySiteSlug (global site slug uniqueness). Run after
adding the bySiteSlug GSI to the DynamoDB table.

Usage:
  python scripts/backfill_gsi4_sites.py --table 9host-main
  python scripts/backfill_gsi4_sites.py --table 9host-main --dry-run
"""

import argparse
import os
import sys

import boto3


def gsi4pk_slug(site_slug: str) -> str:
    return f"SLUG#{site_slug.lower()}"


def gsi4sk_site(site_id: str) -> str:
    return f"SITE#{site_id}"


def backfill(table_name: str, dry_run: bool) -> int:
    """Scan for SITE items missing gsi4pk, add gsi4 keys. Returns count updated."""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Scan for SITE items
    resp = table.scan(
        FilterExpression="begins_with(pk, :pk_prefix) AND begins_with(sk, :sk_prefix)",
        ExpressionAttributeValues={":pk_prefix": "TENANT#", ":sk_prefix": "SITE#"},
    )
    items = resp.get("Items", [])

    while "LastEvaluatedKey" in resp:
        resp = table.scan(
            FilterExpression="begins_with(pk, :pk_prefix) AND begins_with(sk, :sk_prefix)",
            ExpressionAttributeValues={":pk_prefix": "TENANT#", ":sk_prefix": "SITE#"},
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))

    # Filter to items that lack gsi4pk
    to_update = []
    for item in items:
        if item.get("gsi4pk"):
            continue
        sk = item.get("sk", "")
        slug = item.get("slug", "")
        if not sk.startswith("SITE#") or not slug:
            continue
        site_id = sk.replace("SITE#", "")
        to_update.append((item, slug, site_id))

    if not to_update:
        print("No SITE items need gsi4 backfill.")
        return 0

    print(f"Found {len(to_update)} SITE item(s) to backfill.")

    if dry_run:
        for item, slug, site_id in to_update:
            pk = item.get("pk", "")
            print(f"  Would update: {pk} SITE#{site_id} (slug={slug})")
        return 0

    updated = 0
    for item, slug, site_id in to_update:
        table.update_item(
            Key={"pk": item["pk"], "sk": item["sk"]},
            UpdateExpression="SET gsi4pk = :pk, gsi4sk = :sk",
            ExpressionAttributeValues={
                ":pk": gsi4pk_slug(slug),
                ":sk": gsi4sk_site(site_id),
            },
        )
        updated += 1
        pk = item.get("pk", "")
        print(f"  Updated: {pk} SITE#{site_id} (slug={slug})")

    print(f"Backfilled {updated} item(s).")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill gsi4 keys on SITE items")
    parser.add_argument("--table", default=os.environ.get("DYNAMODB_TABLE", "9host-main"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    backfill(args.table, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
