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
from dynamodb_helpers import (
    get_domain_item,
    get_site_item,
    get_tenant_item,
    pk_tenant,
    query_domains_in_tenant,
    sk_domain,
)
from middleware import with_tenant

# Domains: alphanumeric, hyphen, dot; at least one dot; no leading/trailing hyphen or dot
DOMAIN_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$", re.IGNORECASE)

# Tiers that have custom_domains (Pro+)
DOMAINS_TIERS = ("PRO", "BUSINESS")


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


def _extract_domain_from_path(path: str) -> str | None:
    """Extract domain from /api/tenant/domains/{domain}."""
    prefix = "/api/tenant/domains/"
    if path.startswith(prefix):
        rest = path[len(prefix) :].strip("/")
        if rest:
            return unquote(rest).lower()
    return None


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
    return out


def _list_domains(table, tenant_slug: str) -> dict:
    """List domains in tenant."""
    params = query_domains_in_tenant(tenant_slug)
    resp = table.query(**params)
    domains = [_domain_to_response(item) for item in resp.get("Items", [])]
    return _json_response(200, {"domains": domains})


def _get_domain(table, tenant_slug: str, domain: str) -> dict:
    """Get single domain."""
    key = get_domain_item(tenant_slug, domain)
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Domain not found."})
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

    # Task 1.81: DNS verification — CNAME target from env, TXT token per domain
    cname_target = os.environ.get("CLOUDFRONT_CUSTOM_DOMAIN", "").strip()
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
    """Delete domain."""
    key = get_domain_item(tenant_slug, domain)
    resp = table.get_item(Key=key)
    if not resp.get("Item"):
        return _json_response(404, {"error": "Domain not found."})

    table.delete_item(Key=key)
    return _json_response(204, {}, empty_body=True)


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
                "error": "Custom Domains requires Pro or Business tier.",
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

    domain = _extract_domain_from_path(path)
    base_path = "/api/tenant/domains"
    is_list_or_create = path in (base_path, f"{base_path}/")

    if method == "GET" and is_list_or_create:
        return _list_domains(table, tenant_slug)

    if method == "GET" and domain:
        return _get_domain(table, tenant_slug, domain)

    # POST/DELETE require admin or manager (Task 1.24)
    if method in ("POST", "DELETE"):
        if is_cognito:
            ok, err = require_tenant_admin_or_manager(table, sub, tenant_slug)
            if not ok:
                return _json_response(403, {"error": err or "Forbidden."})
        elif not role_is_admin_or_manager(role):
            return _json_response(403, {"error": "Admin or manager role required for this action."})

    if method == "POST" and is_list_or_create:
        body = _parse_body(event) or {}
        return _create_domain(table, tenant_slug, body)

    if method == "DELETE" and domain:
        return _delete_domain(table, tenant_slug, domain)

    return _json_response(405, {"error": "Method not allowed."})
