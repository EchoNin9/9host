# Orangewhip → 9host Data Migration (Task 1.20)

> **When to run:** Only if migrating from an existing orangewhip DynamoDB table with single-user data.

---

## Schema Mapping

| Orangewhip (single-tenant) | 9host (multi-tenant) |
|---------------------------|----------------------|
| `pk=USER#{sub}`, `sk=PROFILE` | `pk=TENANT#{slug}`, `sk=USER#{sub}#PROFILE` |
| Single band/tenant | Default tenant slug (e.g. `default` or band slug) |
| No GSI byUser | Add `gsi1pk=USER#{sub}`, `gsi1sk=TENANT#{slug}#PROFILE` |

---

## Migration Steps

1. **Default tenant:** Create `TENANT#{slug}` item with `sk=TENANT` (name, tier, etc.).
2. **Profile migration:** For each `USER#{sub}` + `PROFILE` item:
   - Create new item: `pk=TENANT#{slug}`, `sk=USER#{sub}#PROFILE`
   - Copy attributes (sub, email, name, role, created_at, updated_at)
   - Add GSI keys: `gsi1pk=USER#{sub}`, `gsi1sk=TENANT#{slug}#PROFILE`
3. **Sites/domains:** If orangewhip had sites under `USER#{sub}`:
   - Migrate to `pk=TENANT#{slug}`, `sk=SITE#{id}` with same attributes.

---

## Script

Run `scripts/migrate_orangewhip_to_9host.py` with:

- `--table` — DynamoDB table name (e.g. `9host-main` or legacy orangewhip table)
- `--tenant-slug` — Default tenant slug for migrated users (default: `default`)
- `--dry-run` — Scan and report only, no writes

If no legacy items exist (pk starting with `USER#`), the script exits with no changes.
