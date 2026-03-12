"""
Sites API — GET/POST/PUT/DELETE /api/tenant/sites.

Tenant-scoped sites CRUD. Requires tenant_slug (header/subdomain), Cognito auth,
tenant membership.
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone

import boto3

from auth_helpers import require_tenant_auth, require_tenant_admin_or_manager, role_is_admin_or_manager
from dynamodb_helpers import (
    get_site_item,
    get_tenant_item,
    get_template_item,
    pk_tenant,
    query_sites_in_tenant,
    sk_site,
)
from middleware import with_tenant

# Slug: lowercase alphanumeric + hyphen
SITE_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


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


def _extract_site_id_from_path(path: str) -> str | None:
    """Extract site_id from /api/tenant/sites/{site_id}."""
    prefix = "/api/tenant/sites/"
    if path.startswith(prefix):
        rest = path[len(prefix) :].strip("/")
        if rest:
            return rest
    return None


def _site_to_response(item: dict) -> dict:
    """Convert DynamoDB item to API response."""
    sk = item.get("sk", "")
    site_id = sk.replace("SITE#", "") if sk.startswith("SITE#") else ""

    return {
        "id": site_id,
        "name": item.get("name", ""),
        "slug": item.get("slug", ""),
        "status": item.get("status", "draft"),
        "template_id": item.get("template_id"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def _tier_rank(tier: str) -> int:
    """Tier rank for comparison. FREE=0, PRO=1, BUSINESS=2."""
    t = (tier or "FREE").upper()
    if t == "FREE":
        return 0
    if t == "PRO":
        return 1
    if t == "BUSINESS":
        return 2
    return 0


def _list_sites(table, tenant_slug: str) -> dict:
    """List sites in tenant."""
    params = query_sites_in_tenant(tenant_slug)
    resp = table.query(**params)
    sites = [_site_to_response(item) for item in resp.get("Items", [])]
    return _json_response(200, {"sites": sites})


def _get_site(table, tenant_slug: str, site_id: str) -> dict:
    """Get single site."""
    key = get_site_item(tenant_slug, site_id)
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Site not found."})
    return _json_response(200, {"site": _site_to_response(item)})


def _create_site(table, tenant_slug: str, body: dict) -> dict:
    """Create site. Optional template_id: validate exists and tenant tier >= template.tier_required (Task 1.32)."""
    name = (body.get("name") or "").strip()
    slug = (body.get("slug") or "").strip().lower()
    status = (body.get("status") or "draft").strip().lower()
    template_id = (body.get("template_id") or "").strip().lower() or None

    if not name:
        return _json_response(400, {"error": "name is required."})

    if status not in ("draft", "published"):
        status = "draft"

    if not slug:
        slug = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))
        if not slug:
            slug = str(uuid.uuid4())[:8]

    if not SITE_SLUG_PATTERN.match(slug):
        return _json_response(400, {"error": "slug must be lowercase alphanumeric + hyphen."})

    # Validate template_id if provided (Task 1.32)
    if template_id:
        template_resp = table.get_item(Key=get_template_item(template_id))
        template_item = template_resp.get("Item")
        if not template_item:
            return _json_response(400, {"error": f"Template not found: {template_id}"})

        tenant_resp = table.get_item(Key=get_tenant_item(tenant_slug))
        tenant_item = tenant_resp.get("Item")
        if not tenant_item:
            return _json_response(404, {"error": "Tenant not found."})

        tenant_tier_rank = _tier_rank(tenant_item.get("tier", "FREE"))
        template_tier_required = template_item.get("tier_required", "FREE")
        if tenant_tier_rank < _tier_rank(template_tier_required):
            return _json_response(
                403,
                {
                    "error": f"Template {template_id} requires {template_tier_required} tier or higher.",
                    "tier_required": template_tier_required,
                    "tenant_tier": tenant_item.get("tier", "FREE"),
                },
            )

    site_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_site(site_id),
        "name": name,
        "slug": slug,
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    if template_id:
        item["template_id"] = template_id

    table.put_item(Item=item)
    return _json_response(201, {"site": _site_to_response(item)})


def _update_site(table, tenant_slug: str, site_id: str, body: dict) -> dict:
    """Update site."""
    key = get_site_item(tenant_slug, site_id)
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Site not found."})

    name = body.get("name")
    slug = body.get("slug")
    status = body.get("status")
    template_id = body.get("template_id")

    if name is not None:
        item["name"] = str(name).strip()
    if slug is not None:
        s = str(slug).strip().lower()
        if not SITE_SLUG_PATTERN.match(s):
            return _json_response(400, {"error": "slug must be lowercase alphanumeric + hyphen."})
        item["slug"] = s
    if status is not None:
        s = str(status).strip().lower()
        if s in ("draft", "published"):
            item["status"] = s
    if template_id is not None:
        tid = (template_id or "").strip().lower() or None
        if tid:
            template_resp = table.get_item(Key=get_template_item(tid))
            if not template_resp.get("Item"):
                return _json_response(400, {"error": f"Template not found: {tid}"})
            tenant_resp = table.get_item(Key=get_tenant_item(tenant_slug))
            tenant_item = tenant_resp.get("Item")
            if tenant_item and _tier_rank(tenant_item.get("tier", "FREE")) < _tier_rank(
                template_resp["Item"].get("tier_required", "FREE")
            ):
                return _json_response(
                    403,
                    {"error": f"Template {tid} requires higher tier."},
                )
            item["template_id"] = tid
        else:
            item.pop("template_id", None)

    item["updated_at"] = datetime.now(timezone.utc).isoformat()

    table.put_item(Item=item)
    return _json_response(200, {"site": _site_to_response(item)})


def _delete_site(table, tenant_slug: str, site_id: str) -> dict:
    """Delete site."""
    key = get_site_item(tenant_slug, site_id)
    resp = table.get_item(Key=key)
    if not resp.get("Item"):
        return _json_response(404, {"error": "Site not found."})

    table.delete_item(Key=key)
    return _json_response(204, {}, empty_body=True)


@with_tenant
def sites_handler(event: dict, context: dict) -> dict:
    """
    GET/POST/PUT/DELETE /api/tenant/sites — tenant-scoped sites CRUD.
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

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    )

    site_id = _extract_site_id_from_path(path)
    base_path = "/api/tenant/sites"
    is_list_or_create = path in (base_path, f"{base_path}/")

    if method == "GET" and is_list_or_create:
        return _list_sites(table, tenant_slug)

    if method == "GET" and site_id:
        return _get_site(table, tenant_slug, site_id)

    # POST/PUT/DELETE require admin or manager (Task 1.24)
    if method in ("POST", "PUT", "DELETE"):
        if is_cognito:
            ok, err = require_tenant_admin_or_manager(table, sub, tenant_slug)
            if not ok:
                return _json_response(403, {"error": err or "Forbidden."})
        elif not role_is_admin_or_manager(role):
            return _json_response(403, {"error": "Admin or manager role required for this action."})

    if method == "POST" and is_list_or_create:
        body = _parse_body(event) or {}
        return _create_site(table, tenant_slug, body)

    if method == "PUT" and site_id:
        body = _parse_body(event) or {}
        return _update_site(table, tenant_slug, site_id, body)

    if method == "DELETE" and site_id:
        return _delete_site(table, tenant_slug, site_id)

    return _json_response(405, {"error": "Method not allowed."})
