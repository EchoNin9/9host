"""
Tenant templates API (Task 1.123, 1.124).

POST /api/tenant/templates/fork — fork a platform template (Pro+)
GET /api/tenant/templates — list tenant's templates
PUT /api/tenant/templates/{slug} — update forked template
DELETE /api/tenant/templates/{slug} — delete forked template
"""

import json
import re
from datetime import datetime, timezone

from dynamodb_helpers import (
    get_tenant_item,
    get_tenant_template_item,
    get_template_item,
    pk_tenant,
    query_tenant_templates,
    sk_template,
)
from request_context import RequestContext
from tenant_store import DynamoDBTenantStore
from tier_config import tier_rank as _tier_rank

TEMPLATE_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
PLATFORM_TENANT = "_platform"
MANAGE_ROLES = ("admin", "manager")


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _template_to_response(item: dict) -> dict:
    sk = item.get("sk", "")
    slug = sk.replace("TEMPLATE#", "") if sk.startswith("TEMPLATE#") else item.get("slug", "")
    return {
        "slug": slug,
        "name": item.get("name", slug),
        "description": item.get("description", ""),
        "tier_required": item.get("tier_required", "FREE"),
        "components": item.get("components") or {},
        "forked_from": item.get("forked_from"),
        "customizations": item.get("customizations") or {},
        "is_custom": True,
    }


def tenant_templates_handler(ctx: RequestContext) -> dict:
    """Route tenant templates: fork, list, get, put, delete."""
    tenant_slug, _ = ctx.require_tenant_member()

    path = ctx.path
    prefix = "/api/tenant/templates"
    if not path.startswith(prefix):
        return _json_response(404, {"error": "Not found."})

    method = ctx.method
    suffix = path[len(prefix) :].strip("/")
    table = DynamoDBTenantStore().table

    if suffix == "fork" and method == "POST":
        ctx.require_tenant_member(MANAGE_ROLES)
        return _fork_handler(ctx.event, table, tenant_slug)
    if not suffix and method == "GET":
        return _list_handler(table, tenant_slug)
    if suffix and "/" not in suffix and method == "GET":
        return _get_handler(table, tenant_slug, suffix)
    if suffix and "/" not in suffix and method == "PUT":
        ctx.require_tenant_member(MANAGE_ROLES)
        return _put_handler(ctx.event, table, tenant_slug, suffix)
    if suffix and "/" not in suffix and method == "DELETE":
        ctx.require_tenant_member(MANAGE_ROLES)
        return _delete_handler(table, tenant_slug, suffix)

    return _json_response(404, {"error": "Not found."})


def _fork_handler(event: dict, table, tenant_slug: str) -> dict:
    """POST /api/tenant/templates/fork — fork platform template. Pro+ only."""
    body = event.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body) if body else {}
        except json.JSONDecodeError:
            body = {}
    body = body or {}

    template_slug = (body.get("template_slug") or body.get("templateSlug") or "").strip().lower()
    name = (body.get("name") or "").strip() or None
    new_slug = (body.get("slug") or "").strip().lower()

    if not template_slug:
        return _json_response(400, {"error": "template_slug is required."})

    tenant_resp = table.get_item(Key=get_tenant_item(tenant_slug))
    tenant_item = tenant_resp.get("Item")
    if not tenant_item:
        return _json_response(404, {"error": "Tenant not found."})
    if _tier_rank(tenant_item.get("tier", "FREE")) < 1:
        return _json_response(403, {"error": "Pro or Business tier required to fork templates."})

    platform_resp = table.get_item(Key=get_template_item(template_slug))
    platform_item = platform_resp.get("Item")
    if not platform_item:
        return _json_response(404, {"error": f"Template not found: {template_slug}"})

    if not new_slug:
        new_slug = f"{template_slug}-custom"
    if not TEMPLATE_SLUG_PATTERN.match(new_slug):
        return _json_response(400, {"error": "slug must be lowercase alphanumeric and hyphen."})
    if len(new_slug) > 60:
        return _json_response(400, {"error": "slug must be at most 60 characters."})

    existing = table.get_item(Key=get_tenant_template_item(tenant_slug, new_slug)).get("Item")
    if existing:
        return _json_response(409, {"error": f"Template slug already exists: {new_slug}"})

    now = datetime.now(timezone.utc).isoformat()
    item = {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_template(new_slug),
        "slug": new_slug,
        "name": name or platform_item.get("name", template_slug),
        "description": platform_item.get("description", ""),
        "tier_required": platform_item.get("tier_required", "FREE"),
        "components": dict(platform_item.get("components") or {}),
        "forked_from": template_slug,
        "customizations": {},
        "created_at": now,
        "updated_at": now,
    }
    table.put_item(Item=item)
    return _json_response(201, {"template": _template_to_response(item)})


def _list_handler(table, tenant_slug: str) -> dict:
    """GET /api/tenant/templates — list tenant's forked templates."""
    resp = table.query(**query_tenant_templates(tenant_slug))
    templates = [_template_to_response(item) for item in resp.get("Items", [])]
    templates.sort(key=lambda t: t["slug"])
    return _json_response(200, {"templates": templates})


def _get_handler(table, tenant_slug: str, slug: str) -> dict:
    """GET /api/tenant/templates/{slug}."""
    resp = table.get_item(Key=get_tenant_template_item(tenant_slug, slug))
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Template not found."})
    return _json_response(200, {"template": _template_to_response(item)})


def _put_handler(event: dict, table, tenant_slug: str, slug: str) -> dict:
    """PUT /api/tenant/templates/{slug} — update forked template."""
    resp = table.get_item(Key=get_tenant_template_item(tenant_slug, slug))
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Template not found."})

    body = event.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body) if body else {}
        except json.JSONDecodeError:
            body = {}
    body = body or {}

    now = datetime.now(timezone.utc).isoformat()
    updates = []
    values = {":now": now}

    for field in ("name", "description"):
        if field in body:
            updates.append(f"{field} = :{field}")
            values[f":{field}"] = str(body[field]) if body[field] is not None else ""

    if "customizations" in body and isinstance(body["customizations"], dict):
        updates.append("customizations = :customizations")
        values[":customizations"] = body["customizations"]

    if "components" in body and isinstance(body["components"], dict):
        updates.append("components = :components")
        values[":components"] = body["components"]

    if not updates:
        return _json_response(400, {"error": "Provide at least one of: name, description, customizations, components"})

    table.update_item(
        Key=get_tenant_template_item(tenant_slug, slug),
        UpdateExpression="SET " + ", ".join(updates) + ", updated_at = :now",
        ExpressionAttributeValues=values,
    )
    updated_resp = table.get_item(Key=get_tenant_template_item(tenant_slug, slug))
    return _json_response(200, {"template": _template_to_response(updated_resp.get("Item", {}))})


def _delete_handler(table, tenant_slug: str, slug: str) -> dict:
    """DELETE /api/tenant/templates/{slug}."""
    table.delete_item(Key=get_tenant_template_item(tenant_slug, slug))
    return {"statusCode": 204, "headers": {"Content-Type": "application/json"}, "body": ""}
