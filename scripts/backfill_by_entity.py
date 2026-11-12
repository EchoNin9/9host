#!/usr/bin/env python3
"""
Backfill byEntity GSI keys (gsi3pk/gsi3sk) on existing tenant and custom-domain rows (T-17).

Tenant rows (sk=TENANT) get gsi3pk=ENTITY#TENANT, domain rows (sk=DOMAIN#{d}) get
gsi3pk=ENTITY#DOMAIN, so the superadmin lists are byEntity Queries instead of Scans. Writes
the MIGRATION#BY_ENTITY marker (TENANT#_platform partition) when done. Idempotent: only rows
without gsi3pk are touched, so re-running is a no-op apart from one filtered Scan.

Delegates to TenantStore.backfill_by_entity (the same code the API runs lazily on the first
superadmin list if this script has not run yet).

Usage:
  python scripts/backfill_by_entity.py --table 9host-main
  python scripts/backfill_by_entity.py --table 9host-main --dry-run
"""

import argparse
import os
import sys

# Allow importing api modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

import boto3

from tenant_store import DynamoDBTenantStore


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Backfill byEntity GSI keys on tenant and domain rows")
    parser.add_argument("--table", default=os.environ.get("DYNAMODB_TABLE", "9host-main"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    store = DynamoDBTenantStore(boto3.resource("dynamodb").Table(args.table))
    counts = store.backfill_by_entity(dry_run=args.dry_run)
    verb = "Would index" if args.dry_run else "Indexed"
    print(f"{verb} {counts['tenants']} tenant row(s) and {counts['domains']} domain row(s) in {args.table}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
