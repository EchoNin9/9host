"""
Custom domain lifecycle (T-07) — Cloudflare for SaaS + HostMappingKVS.

Replaces the ACM certificate / CloudFront alias flow (Tasks 1.146, 1.147). Each
custom domain is a DynamoDB row ``pk=TENANT#{slug}, sk=DOMAIN#{domain}`` that
carries the Cloudflare ``cf_hostname_id``. Lifecycle:

    register_domain(...)       -> row PENDING_VALIDATION with a random verify_token (no Cloudflare yet)
    refresh_domain_status(...) -> SEC-05: until TXT _9host-verify.<domain> = verify_token is seen in DNS,
                                  nothing else happens. Then Cloudflare hostnames are created for the
                                  apex and www.<apex>, each KVS-mapped once active; row ACTIVE with
                                  the apex. Always stamps last_checked_at (poll throttle)
    remove_domain(...)         -> Cloudflare hostnames deleted, KVS keys deleted, row deleted

A dangling CNAME to proxy.echonin9.com is not enough to claim a domain: the TXT token is
random per row, so a removed domain can't be re-claimed by another tenant without fresh DNS.

The Cloudflare port is resolved through ``get_custom_domain_port()`` so tests can
inject a fake (``set_custom_domain_port``).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from cloudflare_saas import (
    CNAME_TARGET,
    CloudflareAPIError,
    CloudflareSaaSAdapter,
    CustomDomainPort,
    CustomHostnameRecord,
)

from tenant_store import entity_keys_domain

logger = logging.getLogger(__name__)

STATUS_PENDING = "PENDING_VALIDATION"
STATUS_ACTIVE = "ACTIVE"
VERIFY_PREFIX = "_9host-verify"

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
    domain = domain_from_item(item)
    validation_records = _load_list(item.get("validation_records")) + _load_list(item.get("www_validation_records"))
    if item.get("verify_token") and not item.get("ownership_verified"):
        validation_records.insert(0, {
            "type": "TXT", "name": f"{VERIFY_PREFIX}.{domain}", "value": item["verify_token"], "purpose": "ownership",
        })
    out = {
        "domain": domain,
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
    if item.get("www"):
        out["www_domain"] = f"www.{domain}"
        out["www_status"] = item.get("www_status", STATUS_PENDING)
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
    """Persist a PENDING domain row (apex + www). Cloudflare is only called once the
    ownership TXT verifies (SEC-05). Caller has validated input, uniqueness and site."""
    now = _now()
    item = {
        "pk": f"TENANT#{tenant_slug}",
        "sk": f"DOMAIN#{domain}",
        "gsi2pk": f"DOMAIN#{domain}",
        "gsi2sk": f"TENANT#{tenant_slug}",
        **entity_keys_domain(tenant_slug, domain),  # byEntity: superadmin list_all_domains (T-17)
        "site_id": site_id,
        "status": STATUS_PENDING,
        "verify_token": uuid.uuid4().hex,
        "www": True,
        "created_at": now,
        "updated_at": now,
    }
    table.put_item(Item=item, ConditionExpression="attribute_not_exists(pk)")
    return item


def txt_values(name: str) -> set[str]:
    """TXT strings published at ``name`` (empty on NXDOMAIN / any DNS error)."""
    import dns.resolver

    try:
        answer = dns.resolver.resolve(name, "TXT", lifetime=3)
    except Exception:  # noqa: BLE001 — unverifiable == not verified
        return set()
    return {b"".join(r.strings).decode("utf-8", "replace") for r in answer}


def domain_hosts(item: dict) -> list[str]:
    """Hostnames a domain row serves: the domain, plus www.<domain> for rows created with it."""
    d = domain_from_item(item)
    return [d, f"www.{d}"] if item.get("www") else [d]


def needs_refresh(item: dict) -> bool:
    """False once the apex is ACTIVE on Cloudflare and www (if any) is too."""
    if (item.get("status") or "").upper() != STATUS_ACTIVE or not item.get("cf_hostname_id"):
        return True
    return bool(item.get("www")) and item.get("www_status") != STATUS_ACTIVE


def _put_mapping(tenant_slug: str, domain: str, site_id: str) -> bool:
    """Write ``domain -> {tenant, site_id}`` into HostMappingKVS. Returns False on failure."""
    import site_storage

    if site_storage.put_host_mapping(domain, tenant_slug, site_id):
        return True
    logger.warning("custom_domain: KVS put failed for %s; leaving PENDING_VALIDATION for retry", domain)
    return False


def _poll(port, cf_id: str | None, hostname: str) -> CustomHostnameRecord:
    return port.get_hostname_status(cf_id) if cf_id else port.register_hostname(hostname)


def refresh_domain_status(table, item: dict, *, raise_errors: bool = False) -> dict:
    """Advance a domain row: ownership TXT -> Cloudflare hostnames -> KVS -> ACTIVE.

    Rows without ``cf_hostname_id`` (new, or legacy ACM-era) are registered with Cloudflare
    once ownership is proven. Legacy rows already ACTIVE are grandfathered. Mutates and
    returns ``item``; progress made before a Cloudflare error is still persisted.
    """
    if not needs_refresh(item):
        return item

    domain, tenant, site_id = domain_from_item(item), tenant_from_item(item), item.get("site_id", "")
    checked_at = _now()
    fields: dict = {"last_checked_at": checked_at, **entity_keys_domain(tenant, domain)}  # self-heal (T-17)
    error: CloudflareAPIError | None = None

    if (item.get("status") or "").upper() == STATUS_ACTIVE:
        fields["ownership_verified"] = True  # grandfathered pre-SEC-05 row
    elif not item.get("ownership_verified"):
        token = fields["verify_token"] = item.get("verify_token") or uuid.uuid4().hex
        if token in txt_values(f"{VERIFY_PREFIX}.{domain}"):
            fields["ownership_verified"] = True

    if item.get("ownership_verified") or fields.get("ownership_verified"):
        port = get_custom_domain_port()
        try:
            if (item.get("status") or "").upper() != STATUS_ACTIVE or not item.get("cf_hostname_id"):
                rec = _poll(port, item.get("cf_hostname_id"), domain)
                fields.update(record_fields(rec))
                if rec.is_active and not _put_mapping(tenant, domain, site_id):
                    fields["status"] = STATUS_PENDING  # retried on next poll
            if item.get("www") and item.get("www_status") != STATUS_ACTIVE:
                rec = _poll(port, item.get("www_cf_hostname_id"), f"www.{domain}")
                fields.update({f"www_{k}": v for k, v in record_fields(rec).items()
                               if k in ("cf_hostname_id", "status", "ssl_status", "validation_records")})
                if rec.is_active and not _put_mapping(tenant, f"www.{domain}", site_id):
                    fields["www_status"] = STATUS_PENDING
        except CloudflareAPIError as e:
            error = e

    fields["updated_at"] = checked_at
    names = {f"#{k}": k for k in fields}
    values = {f":{k}": v for k, v in fields.items()}
    table.update_item(
        Key={"pk": item["pk"], "sk": item["sk"]},
        UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in fields),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )
    item.update(fields)
    if error and raise_errors:
        raise error
    return item


def remove_domain(table, item: dict) -> None:
    """Delete the Cloudflare hostnames, the KVS keys and the DynamoDB row.

    Raises CloudflareAPIError if Cloudflare deletion fails (row kept for retry).
    """
    import site_storage

    for key in ("cf_hostname_id", "www_cf_hostname_id"):
        cf_id = (item.get(key) or "").strip()
        if cf_id:
            get_custom_domain_port().delete_hostname(cf_id)
    for host in domain_hosts(item):
        site_storage.delete_host_mapping(host)  # best-effort, never raises
    table.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
