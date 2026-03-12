#!/usr/bin/env python3
"""
Backfill gsi3pk/gsi3sk on existing USER# items (Task 1.42).

Required for GSI byEntity to list all users across tenants. Run after
adding the byEntity GSI to the DynamoDB table.

Usage:
  python scripts/backfill_gsi3_users.py --table 9host-main
  python scripts/backfill_gsi3_users.py --table 9host-main --dry-run
"""

import argparse
import os
import sys

import boto3


def backfill(table_name: str, dry_run: bool) -> int:
    """Scan for USER# items missing gsi3pk, add gsi3 keys. Returns count updated."""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Scan for USER profile items (sk ends with #PROFILE)
    resp = table.scan(
        FilterExpression="begins_with(pk, :pk_prefix) AND begins_with(sk, :sk_prefix)",
        ExpressionAttributeValues={":pk_prefix": "TENANT#", ":sk_prefix": "USER#"},
    )
    items = resp.get("Items", [])

    while "LastEvaluatedKey" in resp:
        resp = table.scan(
            FilterExpression="begins_with(pk, :pk_prefix) AND begins_with(sk, :sk_prefix)",
            ExpressionAttributeValues={":pk_prefix": "TENANT#", ":sk_prefix": "USER#"},
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))

    # Filter to items that have #PROFILE (not #PERMISSIONS) and lack gsi3pk
    to_update = []
    for item in items:
        sk = item.get("sk", "")
        if not sk.endswith("#PROFILE"):
            continue
        if item.get("gsi3pk"):
            continue
        pk = item.get("pk", "")
        sub = item.get("sub", "")
        if not pk.startswith("TENANT#") or not sub:
            continue
        tenant_slug = pk.replace("TENANT#", "")
        to_update.append((item, tenant_slug, sub))

    if not to_update:
        print("No USER items need gsi3 backfill.")
        return 0

    print(f"Found {len(to_update)} USER item(s) to backfill.")

    if dry_run:
        for item, tenant_slug, sub in to_update:
            print(f"  Would update: TENANT#{tenant_slug} USER#{sub}#PROFILE")
        return 0

    updated = 0
    for item, tenant_slug, sub in to_update:
        table.update_item(
            Key={"pk": item["pk"], "sk": item["sk"]},
            UpdateExpression="SET gsi3pk = :pk, gsi3sk = :sk",
            ExpressionAttributeValues={
                ":pk": "ENTITY#USER",
                ":sk": f"TENANT#{tenant_slug}#USER#{sub}",
            },
        )
        updated += 1
        print(f"  Updated: TENANT#{tenant_slug} USER#{sub}#PROFILE")

    print(f"Backfilled {updated} item(s).")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill gsi3 keys on USER items")
    parser.add_argument("--table", default=os.environ.get("DYNAMODB_TABLE", "9host-main"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    backfill(args.table, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
