"""
Custom domain lifecycle (T-07) — Cloudflare for SaaS + HostMappingKVS.

Replaces the ACM certificate / CloudFront alias flow (Tasks 1.146, 1.147). Each
custom domain is a DynamoDB row ``pk=TENANT#{slug}, sk=DOMAIN#{domain}`` that
carries the Cloudflare ``cf_hostname_id``. Lifecycle:

    register_domain(...)       -> Cloudflare custom hostname created, row PENDING_VALIDATION
    refresh_domain_status(...) -> poll Cloudflare; when active: row ACTIVE + KVS put
    remove_domain(...)         -> Cloudflare hostname deleted, KVS key deleted, row deleted

The Cloudflare port is resolved through ``get_custom_domain_port()`` so tests can
inject a fake (``set_custom_domain_port``).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from cloudflare_saas import (
    CNAME_TARGET,
    CloudflareAPIError,
    CloudflareSaaSAdapter,
    CustomDomainPort,
    CustomHostnameRecord,
)

logger = logging.getLogger(__name__)

STATUS_PENDING = "PENDING_VALIDATION"
STATUS_ACTIVE = "ACTIVE"

_port: CustomDomainPort | None = None


def get_custom_domain_port() -> CustomDomainPort:
    global _port
    if _port is None:
        _port = CloudflareSaaSAdapter()
    return _port


def set_custom_domain_port(port: CustomDomainPort | None) -> None:
    """Override the port (tests). ``None`` resets to the default adapter."""
    global _port
    _port = port


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def domain_from_item(item: dict) -> str:
    sk = item.get("sk", "")
    return sk[len("DOMAIN#"):] if sk.startswith("DOMAIN#") else ""


def tenant_from_item(item: dict) -> str:
    pk = item.get("pk", "")
    return pk[len("TENANT#"):] if pk.startswith("TENANT#") else ""


def _load_list(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            val = json.loads(raw)
        except ValueError:
            return []
        return val if isinstance(val, list) else []
    return list(raw)


def record_fields(rec: CustomHostnameRecord) -> dict:
    """DynamoDB attributes derived from a Cloudflare record."""
    return {
        "cf_hostname_id": rec.cf_hostname_id,
        "cf_status": rec.status,
        "ssl_status": rec.ssl_status,
        "verification_cname_target": rec.cname_target,
        "validation_records": json.dumps(rec.validation_records),
        "verification_errors": json.dumps(rec.verification_errors),
        "status": STATUS_ACTIVE if rec.is_active else STATUS_PENDING,
    }


def domain_to_response(item: dict) -> dict:
    """Public API shape for a domain row (frontend contract)."""
    validation_records = _load_list(item.get("validation_records"))
    out = {
        "domain": domain_from_item(item),
        "site_id": item.get("site_id", ""),
        "status": item.get("status", "pending"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
        "cname_target": CNAME_TARGET,
        "verification_cname_target": CNAME_TARGET,
        "validation_records": validation_records,
        # Back-compat alias: the existing wizard renders {type, name, value} rows from here.
        "acm_validation_records": validation_records,
    }
    if item.get("cf_hostname_id"):
        out["cf_hostname_id"] = item["cf_hostname_id"]
    if item.get("cf_status"):
        out["cf_status"] = item["cf_status"]
    if item.get("ssl_status"):
        out["ssl_status"] = item["ssl_status"]
    errors = _load_list(item.get("verification_errors"))
    if errors:
        out["verification_errors"] = errors
    return out


def register_domain(table, tenant_slug: str, domain: str, site_id: str) -> dict:
    """Create the Cloudflare custom hostname and persist the domain row.

    Caller has already validated input, uniqueness and site existence.
    Raises CloudflareAPIError on provider failure (no row is written).
    """
    port = get_custom_domain_port()
    rec = port.register_hostname(domain)
    now = _now()
    item = {
        "pk": f"TENANT#{tenant_slug}",
        "sk": f"DOMAIN#{domain}",
        "gsi2pk": f"DOMAIN#{domain}",
        "gsi2sk": f"TENANT#{tenant_slug}",
        "site_id": site_id,
        "created_at": now,
        "updated_at": now,
        **_fields_for(rec, tenant_slug, domain, site_id),
    }
    try:
        table.put_item(Item=item, ConditionExpression="attribute_not_exists(pk)")
    except Exception:
        # Don't leak a Cloudflare hostname we have no row for.
        try:
            port.delete_hostname(rec.cf_hostname_id)
        except CloudflareAPIError:
            logger.warning("custom_domain: rollback delete failed for %s", domain)
        raise
    return item


def _put_mapping(tenant_slug: str, domain: str, site_id: str) -> bool:
    """Write ``domain -> {tenant, site_id}`` into HostMappingKVS. Returns False on failure."""
    from site_storage import put_host_mapping

    try:
        put_host_mapping(domain, tenant_slug, site_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("custom_domain: KVS put failed for %s: %s", domain, type(exc).__name__)
        return False
    return True


def _fields_for(rec: CustomHostnameRecord, tenant_slug: str, domain: str, site_id: str) -> dict:
    """Row attributes for ``rec``; only ACTIVE once the KVS mapping is written."""
    fields = record_fields(rec)
    if rec.is_active and not _put_mapping(tenant_slug, domain, site_id):
        fields["status"] = STATUS_PENDING  # retried on next poll
    return fields


def refresh_domain_status(table, item: dict, *, raise_errors: bool = False) -> dict:
    """Poll Cloudflare for a non-ACTIVE domain row and persist the result.

    Rows without ``cf_hostname_id`` (legacy ACM-era rows) are registered with
    Cloudflare first. Mutates and returns ``item``.
    """
    if (item.get("status") or "").upper() == STATUS_ACTIVE and item.get("cf_hostname_id"):
        return item

    port = get_custom_domain_port()
    try:
        if item.get("cf_hostname_id"):
            rec = port.get_hostname_status(item["cf_hostname_id"])
        else:
            rec = port.register_hostname(domain_from_item(item))
    except CloudflareAPIError:
        if raise_errors:
            raise
        return item

    fields = _fields_for(rec, tenant_from_item(item), domain_from_item(item), item.get("site_id", ""))
    fields["updated_at"] = _now()
    names = {f"#{k}": k for k in fields}
    values = {f":{k}": v for k, v in fields.items()}
    table.update_item(
        Key={"pk": item["pk"], "sk": item["sk"]},
        UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in fields),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )
    item.update(fields)
    return item


def remove_domain(table, item: dict) -> None:
    """Delete the Cloudflare hostname, the KVS key and the DynamoDB row.

    Raises CloudflareAPIError if Cloudflare deletion fails (row kept for retry).
    """
    from site_storage import delete_host_mapping

    domain = domain_from_item(item)
    cf_id = (item.get("cf_hostname_id") or "").strip()
    if cf_id:
        get_custom_domain_port().delete_hostname(cf_id)
    try:
        delete_host_mapping(domain)
    except Exception as exc:  # noqa: BLE001 - hostname is gone at Cloudflare; traffic can't reach us
        logger.warning("custom_domain: KVS delete failed for %s: %s", domain, type(exc).__name__)
    table.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
