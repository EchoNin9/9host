#!/usr/bin/env python3
"""
Orangewhip → 9host data migration (Task 1.20).

Migrates single-user schema (USER#{sub} + PROFILE) to multi-tenant
(TENANT#{slug}#USER#{sub}#PROFILE). Run only if legacy orangewhip data exists.

Usage:
  python scripts/migrate_orangewhip_to_9host.py --table 9host-main --tenant-slug default
  python scripts/migrate_orangewhip_to_9host.py --table 9host-main --dry-run
"""

import argparse
import os
import sys
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def pk_tenant(slug: str) -> str:
    return f"TENANT#{slug}"


def sk_tenant() -> str:
    return "TENANT"


def sk_user_profile(sub: str) -> str:
    return f"USER#{sub}#PROFILE"


def gsi1pk_user(sub: str) -> str:
    return f"USER#{sub}"


def gsi1sk_tenant_profile(slug: str) -> str:
    return f"TENANT#{slug}#PROFILE"


def migrate(table_name: str, tenant_slug: str, dry_run: bool) -> int:
    """Scan for legacy USER# items, migrate to TENANT# format. Returns count migrated."""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Scan for legacy profile items: pk begins_with USER#, sk = PROFILE
    resp = table.scan(
        FilterExpression="begins_with(pk, :pk_prefix) AND sk = :sk",
        ExpressionAttributeValues={":pk_prefix": "USER#", ":sk": "PROFILE"},
    )
    items = resp.get("Items", [])

    # Paginate if needed
    while "LastEvaluatedKey" in resp:
        resp = table.scan(
            FilterExpression="begins_with(pk, :pk_prefix) AND sk = :sk",
            ExpressionAttributeValues={":pk_prefix": "USER#", ":sk": "PROFILE"},
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp.get("Items", []))

    if not items:
        print("No legacy orangewhip data found. Nothing to migrate.")
        return 0

    print(f"Found {len(items)} legacy profile(s) to migrate.")

    if dry_run:
        for item in items:
            sub = item.get("pk", "").replace("USER#", "")
            print(f"  Would migrate: USER#{sub} -> TENANT#{tenant_slug}#USER#{sub}#PROFILE")
        return 0

    now = datetime.now(timezone.utc).isoformat()

    # Ensure tenant exists (create if not). owner_sub set from first migrated user.
    tenant_key = {"pk": pk_tenant(tenant_slug), "sk": sk_tenant()}
    first_sub = items[0].get("pk", "").replace("USER#", "") if items else None
    try:
        table.put_item(
            Item={
                **tenant_key,
                "name": tenant_slug.replace("-", " ").title(),
                "tier": "FREE",
                "owner_sub": first_sub,
                "created_at": now,
                "updated_at": now,
            },
            ConditionExpression="attribute_not_exists(pk)",
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        # Tenant already exists

    migrated = 0
    for item in items:
        old_pk = item.get("pk", "")
        if not old_pk.startswith("USER#"):
            continue
        sub = old_pk.replace("USER#", "")
        if not sub:
            continue

        new_item = {
            "pk": pk_tenant(tenant_slug),
            "sk": sk_user_profile(sub),
            "gsi1pk": gsi1pk_user(sub),
            "gsi1sk": gsi1sk_tenant_profile(tenant_slug),
            "sub": sub,
            "email": item.get("email", ""),
            "name": item.get("name", ""),
            "role": item.get("role", "admin"),
            "created_at": item.get("created_at", now),
            "updated_at": now,
        }
        table.put_item(Item=new_item)
        migrated += 1
        print(f"  Migrated: USER#{sub} -> TENANT#{tenant_slug}#USER#{sub}#PROFILE")

    print(f"Migrated {migrated} profile(s).")
    return migrated


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate orangewhip data to 9host multi-tenant")
    parser.add_argument("--table", default=os.environ.get("DYNAMODB_TABLE", "9host-main"))
    parser.add_argument("--tenant-slug", default="default")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    migrate(args.table, args.tenant_slug, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
