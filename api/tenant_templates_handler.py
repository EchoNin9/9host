"""
Tenant templates API (Task 1.123, 1.124).

POST /api/tenant/templates/fork — fork a platform template (Pro+)
GET /api/tenant/templates — list tenant's templates
PUT /api/tenant/templates/{slug} — update forked template
DELETE /api/tenant/templates/{slug} — delete forked template
"""

import json
import os
import re
from datetime import datetime, timezone

import boto3

from auth_helpers import require_tenant_admin_or_manager, require_tenant_auth
from dynamodb_helpers import (
    get_tenant_item,
    get_tenant_template_item,
    get_template_item,
    pk_tenant,
    query_tenant_templates,
    sk_template,
)
from middleware import with_tenant
from tier_config import tier_rank as _tier_rank

TEMPLATE_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")
PLATFORM_TENANT = "_platform"


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


@with_tenant
def tenant_templates_handler(event: dict, context: dict) -> dict:
    """Route tenant templates: fork, list, get, put, delete."""
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(400, {"error": "Missing tenant."})

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    prefix = "/api/tenant/templates"
    if not path.startswith(prefix):
        return _json_response(404, {"error": "Not found."})

    method = (event.get("requestContext", {}).get("http", {}).get("method") or "GET").upper()
    suffix = path[len(prefix) :].strip("/")

    if suffix == "fork" and method == "POST":
        return _fork_handler(event, context, tenant_slug)
    if not suffix and method == "GET":
        return _list_handler(event, context, tenant_slug)
    if suffix and "/" not in suffix and method == "GET":
        return _get_handler(event, context, tenant_slug, suffix)
    if suffix and "/" not in suffix and method == "PUT":
        return _put_handler(event, context, tenant_slug, suffix)
    if suffix and "/" not in suffix and method == "DELETE":
        return _delete_handler(event, context, tenant_slug, suffix)

    return _json_response(404, {"error": "Not found."})


def _fork_handler(event: dict, context: dict, tenant_slug: str) -> dict:
    """POST /api/tenant/templates/fork — fork platform template. Pro+ only."""
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

    if is_cognito:
        ok, err = require_tenant_admin_or_manager(table, sub_or_username, tenant_slug, event)
        if not ok:
            return _json_response(403, {"error": err or "Forbidden."})

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


def _list_handler(event: dict, context: dict, tenant_slug: str) -> dict:
    """GET /api/tenant/templates — list tenant's forked templates."""
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

    resp = table.query(**query_tenant_templates(tenant_slug))
    templates = [_template_to_response(item) for item in resp.get("Items", [])]
    templates.sort(key=lambda t: t["slug"])
    return _json_response(200, {"templates": templates})


def _get_handler(event: dict, context: dict, tenant_slug: str, slug: str) -> dict:
    """GET /api/tenant/templates/{slug}."""
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

    resp = table.get_item(Key=get_tenant_template_item(tenant_slug, slug))
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": "Template not found."})
    return _json_response(200, {"template": _template_to_response(item)})


def _put_handler(event: dict, context: dict, tenant_slug: str, slug: str) -> dict:
    """PUT /api/tenant/templates/{slug} — update forked template."""
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

    if is_cognito:
        ok, err = require_tenant_admin_or_manager(table, sub_or_username, tenant_slug, event)
        if not ok:
            return _json_response(403, {"error": err or "Forbidden."})

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


def _delete_handler(event: dict, context: dict, tenant_slug: str, slug: str) -> dict:
    """DELETE /api/tenant/templates/{slug}."""
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

    if is_cognito:
        ok, err = require_tenant_admin_or_manager(table, sub_or_username, tenant_slug, event)
        if not ok:
            return _json_response(403, {"error": err or "Forbidden."})

    table.delete_item(Key=get_tenant_template_item(tenant_slug, slug))
    return {"statusCode": 204, "headers": {"Content-Type": "application/json"}, "body": ""}
