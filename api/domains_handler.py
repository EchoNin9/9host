"""
Domains API — GET/POST/DELETE /api/tenant/domains.

Custom domains (Pro+ tier, ``custom_domains`` feature). Requires tenant_slug
(header/subdomain), Cognito/TUSER auth, tenant membership, tier >= Pro.

T-07: domains are provisioned as Cloudflare for SaaS custom hostnames
(``CNAME -> proxy.echo9.net``) via ``custom_domain_handler`` / ``CloudflareSaaSAdapter``;
ACTIVE domains are mapped in HostMappingKVS. No ACM / CloudFront alias calls.
"""

import json
import os
from urllib.parse import unquote

import boto3
from boto3.dynamodb.conditions import Key

from auth_helpers import require_tenant_auth, require_tenant_admin_or_manager, role_is_admin_or_manager
from cloudflare_saas import CloudflareAPIError, InvalidDomainError, validate_domain
from custom_domain_handler import (
    STATUS_ACTIVE,
    domain_to_response,
    refresh_domain_status,
    register_domain,
    remove_domain,
)
from dynamodb_helpers import (
    get_domain_item,
    get_tenant_item,
    gsi2pk_domain,
    query_domains_in_tenant,
)
from middleware import with_tenant
from tenant_store import DynamoDBTenantStore
from tier_config import tiers_with_pro_features

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


def _cf_error_response(err: CloudflareAPIError) -> dict:
    return _json_response(err.http_status, err.to_response_body())


def _domain_in_use(table, domain: str) -> bool:
    """Global uniqueness via the byDomain GSI (domain -> tenant)."""
    resp = table.query(
        IndexName="byDomain",
        KeyConditionExpression=Key("gsi2pk").eq(gsi2pk_domain(domain)),
        Limit=1,
    )
    return bool(resp.get("Items"))


def _refresh_pending(table, items: list[dict]) -> list[dict]:
    """Poll Cloudflare for non-ACTIVE domains (best-effort; errors keep stored status)."""
    for item in items:
        if (item.get("status") or "").upper() != STATUS_ACTIVE or not item.get("cf_hostname_id"):
            refresh_domain_status(table, item)
    return items


def _list_domains(table, tenant_slug: str) -> dict:
    """List domains in tenant, refreshing pending ones from Cloudflare."""
    resp = table.query(**query_domains_in_tenant(tenant_slug))
    items = _refresh_pending(table, resp.get("Items", []))
    return _json_response(200, {"domains": [domain_to_response(i) for i in items]})


def _get_item(table, tenant_slug: str, domain: str) -> dict | None:
    return table.get_item(Key=get_domain_item(tenant_slug, domain)).get("Item")


def _get_domain(table, tenant_slug: str, domain: str) -> dict:
    item = _get_item(table, tenant_slug, domain)
    if not item:
        return _json_response(404, {"error": "Domain not found."})
    _refresh_pending(table, [item])
    return _json_response(200, {"domain": domain_to_response(item)})


def _create_domain(table, tenant_slug: str, body: dict) -> dict:
    """Validate, register with Cloudflare, persist row (status PENDING_VALIDATION)."""
    site_id = (body.get("site_id") or "").strip()
    if not (body.get("domain") or "").strip():
        return _json_response(400, {"error": "domain is required."})
    if not site_id:
        return _json_response(400, {"error": "site_id is required."})
    try:
        domain = validate_domain(body.get("domain"))
    except InvalidDomainError as e:
        return _json_response(400, {"error": str(e)})

    if DynamoDBTenantStore(table).get_site(tenant_slug, site_id) is None:
        return _json_response(404, {"error": "Site not found."})

    if _get_item(table, tenant_slug, domain):
        return _json_response(409, {"error": "Domain already exists for this tenant."})
    if _domain_in_use(table, domain):
        return _json_response(409, {"error": "Domain is already in use by another site."})

    try:
        item = register_domain(table, tenant_slug, domain, site_id)
    except CloudflareAPIError as e:
        return _cf_error_response(e)

    return _json_response(
        201,
        {
            "domain": domain_to_response(item),
            "message": f"Add a CNAME record pointing {domain} to {domain_to_response(item)['cname_target']}.",
        },
    )


def _delete_domain(table, tenant_slug: str, domain: str) -> dict:
    """Delete Cloudflare hostname + KVS mapping + row."""
    item = _get_item(table, tenant_slug, domain)
    if not item:
        return _json_response(404, {"error": "Domain not found."})
    try:
        remove_domain(table, item)
    except CloudflareAPIError as e:
        return _cf_error_response(e)
    return _json_response(204, {}, empty_body=True)


def _activate_domain(table, tenant_slug: str, domain: str) -> dict:
    """Re-check Cloudflare status now (registers legacy rows lacking cf_hostname_id)."""
    item = _get_item(table, tenant_slug, domain)
    if not item:
        return _json_response(404, {"error": "Domain not found."})
    if (item.get("status") or "").upper() == STATUS_ACTIVE and item.get("cf_hostname_id"):
        return _json_response(400, {"error": "Domain already ACTIVE. No activation needed."})
    try:
        refresh_domain_status(table, item, raise_errors=True)
    except CloudflareAPIError as e:
        return _cf_error_response(e)

    out = domain_to_response(item)
    if out["status"] == STATUS_ACTIVE:
        message = "Domain is active."
    else:
        message = (
            f"Point a CNAME for {domain} to {out['cname_target']}. If you cannot use a CNAME "
            "(apex domain), add the TXT validation records. SSL is issued automatically once verified."
        )
    return _json_response(
        200,
        {
            "domain": out,
            "validation_records": out["validation_records"],
            "acm_validation_records": out["validation_records"],
            "message": message,
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

    # POST /api/tenant/domains/{domain}/activate — re-check Cloudflare custom hostname status
    if method == "POST" and domain and path_suffix == "activate":
        return _activate_domain(table, tenant_slug, domain)

    return _json_response(405, {"error": "Method not allowed."})
