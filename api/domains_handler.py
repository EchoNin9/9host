"""
Domains API — GET/POST/DELETE /api/tenant/domains.

Custom domains (Pro+ tier). Requires tenant_slug (header/subdomain), Cognito auth,
tenant membership, tier >= Pro.
"""

import json
import os
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import unquote

import boto3

from auth_helpers import require_tenant_auth, require_tenant_admin_or_manager, role_is_admin_or_manager
from custom_domain_handler import (
    add_cloudfront_alias,
    create_custom_domain_distribution,
    delete_acm_certificate,
    disable_custom_domain_distribution,
    remove_cloudfront_alias,
    request_acm_certificate,
)
from dynamodb_helpers import (
    get_domain_item,
    get_site_item,
    get_tenant_item,
    pk_tenant,
    query_domains_in_tenant,
    sk_domain,
)
from middleware import with_tenant
from tier_config import tiers_with_pro_features

# Domains: alphanumeric, hyphen, dot; at least one dot; no leading/trailing hyphen or dot
DOMAIN_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$", re.IGNORECASE)

# Tiers that have custom_domains (Pro+), includes VIP (Task 1.82)
DOMAINS_TIERS = tiers_with_pro_features()


def _json_response(status: int, body: dict, empty_body: bool = False) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": "" if empty_body else json.dumps(body),
    }


def _parse_body(event: dict) -> dict | None:
    """Parse JSON body from event."""
    body = event.get("body")
    if not body:
        return None
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None
    return body


def _extract_domain_from_path(path: str) -> tuple[str | None, str]:
    """Extract domain and path suffix from /api/tenant/domains/{domain}[/activate]."""
    prefix = "/api/tenant/domains/"
    if path.startswith(prefix):
        rest = path[len(prefix) :].strip("/")
        if rest:
            parts = rest.split("/")
            domain = unquote(parts[0]).lower()
            suffix = "/".join(parts[1:]) if len(parts) > 1 else ""
            return domain, suffix
    return None, ""


def _domain_to_response(item: dict) -> dict:
    """Convert DynamoDB item to API response."""
    sk = item.get("sk", "")
    domain = sk.replace("DOMAIN#", "") if sk.startswith("DOMAIN#") else ""

    out = {
        "domain": domain,
        "site_id": item.get("site_id", ""),
        "status": item.get("status", "pending"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }
    # Task 1.81: DNS verification fields for Domain Setup Guide
    if item.get("verification_cname_target"):
        out["verification_cname_target"] = item["verification_cname_target"]
    if item.get("verification_txt_record"):
        out["verification_txt_record"] = item["verification_txt_record"]
    # Task 1.99/1.100: ACM cert ARN when requested
    if item.get("acm_certificate_arn"):
        out["acm_certificate_arn"] = item["acm_certificate_arn"]
    # Task 1.146: ACM validation records (persisted for frontend display)
    if item.get("acm_validation_records"):
        raw = item["acm_validation_records"]
        out["acm_validation_records"] = json.loads(raw) if isinstance(raw, str) else raw
    # Per-domain CloudFront distribution (custom-domain-distro)
    if item.get("cloudfront_distribution_id"):
        out["cloudfront_distribution_id"] = item["cloudfront_distribution_id"]
    if item.get("cloudfront_domain_name"):
        out["cloudfront_domain_name"] = item["cloudfront_domain_name"]
    return out


def _check_pending_certs(table, items: list[dict]) -> list[dict]:
    """Check ACM status for PENDING_VALIDATION domains; promote to ACTIVE if cert is ISSUED."""
    pending = [i for i in items if (i.get("status") or "").upper() == "PENDING_VALIDATION" and i.get("acm_certificate_arn")]
    if not pending:
        return items

    acm = boto3.client("acm", region_name="us-east-1")
    for item in pending:
        cert_arn = item["acm_certificate_arn"]
        try:
            desc = acm.describe_certificate(CertificateArn=cert_arn)
            cert_status = desc.get("Certificate", {}).get("Status", "")
        except Exception:
            continue

        if cert_status == "ISSUED":
            sk = item.get("sk", "")
            domain = sk.replace("DOMAIN#", "") if sk.startswith("DOMAIN#") else ""
            pk = item.get("pk", "")
            tenant_slug = pk.replace("TENANT#", "") if pk.startswith("TENANT#") else ""
            site_id = item.get("site_id", "")

            # Create per-domain CloudFront distribution (if not already created)
            update_expr = "SET #status = :status, updated_at = :now"
            expr_vals: dict = {":status": "ACTIVE", ":now": datetime.now(timezone.utc).isoformat()}
            expr_names: dict = {"#status": "status"}

            if not item.get("cloudfront_distribution_id") and tenant_slug and site_id:
                try:
                    dist_info = create_custom_domain_distribution(
                        domain=domain,
                        cert_arn=cert_arn,
                        tenant=tenant_slug,
                        site_id=site_id,
                    )
                    update_expr += ", cloudfront_distribution_id = :dist_id, cloudfront_domain_name = :dist_dn"
                    expr_vals[":dist_id"] = dist_info["distribution_id"]
                    expr_vals[":dist_dn"] = dist_info["domain_name"]
                    item["cloudfront_distribution_id"] = dist_info["distribution_id"]
                    item["cloudfront_domain_name"] = dist_info["domain_name"]
                except RuntimeError as e:
                    print(f"[9host] Distribution creation failed for {domain}: {e}")
                    continue

            key = {"pk": item["pk"], "sk": item["sk"]}
            table.update_item(
                Key=key,
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_vals,
            )
            item["status"] = "ACTIVE"
            item["updated_at"] = expr_vals[":now"]

    return items


def _list_domains(table, tenant_slug: str) -> dict:
    """List domains in tenant. Checks ACM for any PENDING_VALIDATION certs."""
    params = query_domains_in_tenant(tenant_slug)
    resp = table.query(**params)
    items = resp.get("Items", [])
    items = _check_pending_certs(table, items)
    domains = [_domain_to_response(item) for item in items]
    return _json_response(200, {"domains": domains})


def _get_domain(table, tenant_slug: str, domain: str) -> dict:
    """Get single domain. Checks ACM if PENDING_VALIDATION."""
    key = get_domain_item(tenant_slug, domain)
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Domain not found."})
    _check_pending_certs(table, [item])
    return _json_response(200, {"domain": _domain_to_response(item)})


def _create_domain(table, tenant_slug: str, body: dict) -> dict:
    """Create domain."""
    domain_raw = (body.get("domain") or "").strip().lower()
    site_id = (body.get("site_id") or "").strip()
    status = (body.get("status") or "pending").strip().lower()

    if not domain_raw:
        return _json_response(400, {"error": "domain is required."})

    if not site_id:
        return _json_response(400, {"error": "site_id is required."})

    if status not in ("pending", "verified"):
        status = "pending"

    if not DOMAIN_PATTERN.match(domain_raw):
        return _json_response(
            400,
            {"error": "domain must be a valid domain (e.g. example.com, blog.example.com)."},
        )

    # Verify site exists in tenant
    site_resp = table.get_item(Key=get_site_item(tenant_slug, site_id))
    if not site_resp.get("Item"):
        return _json_response(404, {"error": "Site not found."})

    # Check domain not already in use (in this tenant)
    key = get_domain_item(tenant_slug, domain_raw)
    existing = table.get_item(Key=key)
    if existing.get("Item"):
        return _json_response(409, {"error": "Domain already exists for this tenant."})

    now = datetime.now(timezone.utc).isoformat()

    # Task 1.81: DNS verification — CNAME target (sites distribution for custom domains)
    cname_target = (
        os.environ.get("CLOUDFRONT_SITES_DOMAIN") or os.environ.get("CLOUDFRONT_CUSTOM_DOMAIN", "")
    ).strip()
    txt_token = secrets.token_hex(8)
    verification_txt = f"9host-verify={txt_token}"

    item = {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_domain(domain_raw),
        "gsi2pk": f"DOMAIN#{domain_raw}",
        "gsi2sk": f"TENANT#{tenant_slug}",
        "site_id": site_id,
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    if cname_target:
        item["verification_cname_target"] = cname_target
    item["verification_txt_record"] = verification_txt

    table.put_item(Item=item)
    return _json_response(201, {"domain": _domain_to_response(item)})


def _delete_domain(table, tenant_slug: str, domain: str) -> dict:
    """Delete domain. Cleans up CloudFront alias and ACM cert (Task 1.147)."""
    key = get_domain_item(tenant_slug, domain)
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Domain not found."})

    # Disable per-domain CloudFront distribution (aliases removed so domain is freed)
    dist_id = (item.get("cloudfront_distribution_id") or "").strip()
    if dist_id:
        disable_custom_domain_distribution(dist_id)

    # Legacy: remove alias from shared sites distribution (migration compat)
    status = (item.get("status") or "").upper()
    if status == "ACTIVE" and not dist_id:
        remove_cloudfront_alias(domain)

    # Delete ACM certificate (best-effort; may fail if still in use by distribution)
    cert_arn = (item.get("acm_certificate_arn") or "").strip()
    if cert_arn:
        delete_acm_certificate(cert_arn)

    table.delete_item(Key=key)
    return _json_response(204, {}, empty_body=True)


def _verify_dns_ownership(domain: str, cname_target: str, txt_record: str) -> bool:
    """Verify domain ownership via CNAME or TXT. Returns True if either passes."""
    try:
        import dns.resolver
    except ImportError:
        return False

    # CNAME: domain should resolve to cname_target (or be a CNAME to it)
    if cname_target:
        cname_target_norm = cname_target.rstrip(".").lower()
        try:
            answers = dns.resolver.resolve(domain, "CNAME")
            for rdata in answers:
                target = str(rdata.target).rstrip(".").lower()
                if target == cname_target_norm or target.endswith("." + cname_target_norm):
                    return True
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            pass

    # TXT: _9host-verify.{domain} should have our TXT value
    if txt_record:
        verify_host = f"_9host-verify.{domain}"
        try:
            answers = dns.resolver.resolve(verify_host, "TXT")
            for rdata in answers:
                txt_val = "".join(s.decode("utf-8") if isinstance(s, bytes) else s for s in rdata.strings).strip('"')
                if txt_record in txt_val or txt_val == txt_record:
                    return True
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            pass

    return False


def _activate_domain(event: dict, table, tenant_slug: str, domain: str) -> dict:
    """Task 1.100: On DNS verify pass, request ACM cert, store ARN, status PENDING_VALIDATION."""
    key = get_domain_item(tenant_slug, domain)
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Domain not found."})

    status = (item.get("status") or "pending").upper()
    if status == "ACTIVE":
        return _json_response(400, {"error": "Domain already ACTIVE. No activation needed."})
    if status == "PENDING_VALIDATION":
        # Check if cert was issued while waiting — promote to ACTIVE
        _check_pending_certs(table, [item])
        return _json_response(200, {"domain": _domain_to_response(item)})

    cname_target = (item.get("verification_cname_target") or "").strip()
    txt_record = (item.get("verification_txt_record") or "").strip()
    if not cname_target and not txt_record:
        return _json_response(
            400,
            {"error": "No verification records. Add domain with verification_cname_target or verification_txt_record."},
        )

    if not _verify_dns_ownership(domain, cname_target, txt_record):
        return _json_response(
            400,
            {
                "error": "DNS verification failed. Add the CNAME or TXT record at your DNS provider, then try again.",
            },
        )

    # Task 1.146: Use centralized cert request from custom_domain_handler
    try:
        cert_arn, validation_records = request_acm_certificate(domain)
    except RuntimeError as e:
        return _json_response(500, {"error": str(e)})

    # Persist validation records in DynamoDB so frontend can display them (Task 1.146)
    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key=key,
        UpdateExpression="SET #status = :status, acm_certificate_arn = :arn, acm_validation_records = :recs, updated_at = :now",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": "PENDING_VALIDATION",
            ":arn": cert_arn,
            ":recs": json.dumps(validation_records),
            ":now": now,
        },
    )

    updated = dict(item)
    updated["status"] = "PENDING_VALIDATION"
    updated["acm_certificate_arn"] = cert_arn
    updated["acm_validation_records"] = validation_records
    updated["updated_at"] = now

    return _json_response(
        200,
        {
            "domain": _domain_to_response(updated),
            "acm_validation_records": validation_records,
            "message": "Add the ACM validation CNAME records above to your DNS. Certificate will activate when validated.",
        },
    )


@with_tenant
def domains_handler(event: dict, context: dict) -> dict:
    """
    GET/POST/DELETE /api/tenant/domains — tenant-scoped custom domains (Pro+).
    Requires tenant_slug (X-Tenant-Slug or subdomain), Cognito auth, tenant membership.
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(
            400,
            {"error": "Missing tenant. Use subdomain or X-Tenant-Slug header."},
        )

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    region = os.environ.get("AWS_REGION", "us-east-1")
    auth_result = require_tenant_auth(event, table, tenant_slug, region)
    if auth_result[0] is not True:
        _, err_resp = auth_result
        return _json_response(err_resp.get("statusCode", 401), json.loads(err_resp.get("body", "{}")))
    _, sub_or_username, role, is_cognito = auth_result
    sub = sub_or_username if is_cognito else None

    # Get tenant to check tier (Pro+ for custom domains)
    tenant_resp = table.get_item(Key=get_tenant_item(tenant_slug))
    tenant = tenant_resp.get("Item")
    tier = (tenant or {}).get("tier", "FREE").upper()

    if tier not in DOMAINS_TIERS:
        return _json_response(
            403,
            {
                "error": "Custom Domains requires Pro, Business, or VIP tier.",
                "tier": tier,
                "upgrade_required": True,
            },
        )

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    )

    domain, path_suffix = _extract_domain_from_path(path)
    base_path = "/api/tenant/domains"
    is_list_or_create = path in (base_path, f"{base_path}/")

    if method == "GET" and is_list_or_create:
        return _list_domains(table, tenant_slug)

    if method == "GET" and domain and not path_suffix:
        return _get_domain(table, tenant_slug, domain)

    # POST/DELETE/activate require admin or manager (Task 1.24)
    if method in ("POST", "DELETE"):
        if is_cognito:
            ok, err = require_tenant_admin_or_manager(table, sub, tenant_slug, event)
            if not ok:
                return _json_response(403, {"error": err or "Forbidden."})
        elif not role_is_admin_or_manager(role):
            return _json_response(403, {"error": "Admin or manager role required for this action."})

    if method == "POST" and is_list_or_create:
        body = _parse_body(event) or {}
        return _create_domain(table, tenant_slug, body)

    if method == "DELETE" and domain and not path_suffix:
        return _delete_domain(table, tenant_slug, domain)

    # Task 1.100: POST /api/tenant/domains/{domain}/activate — DNS verify + request ACM cert
    if method == "POST" and domain and path_suffix == "activate":
        return _activate_domain(event, table, tenant_slug, domain)

    return _json_response(405, {"error": "Method not allowed."})
