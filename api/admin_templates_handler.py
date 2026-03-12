"""
Superadmin templates CRUD — GET/POST/PUT/DELETE /api/admin/templates (Task 1.31).

Requires Cognito auth and superadmin group membership.
"""

import json
import os
from datetime import datetime, timezone

import boto3

from auth_helpers import get_sub_from_access_token, is_superadmin
from dynamodb_helpers import get_template_item, pk_tenant, query_templates, sk_template

PLATFORM_TENANT = "_platform"


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _require_superadmin(event: dict) -> tuple[str | None, dict | None]:
    """Require authenticated superadmin. Returns (sub, None) if ok, (None, error_response) if not."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    user_pool_id = os.environ.get("USER_POOL_ID", "")

    sub = get_sub_from_access_token(event, region=region)
    if not sub:
        return None, _json_response(
            401,
            {"error": "Unauthorized. Provide Authorization: Bearer <access_token>."},
        )

    if not is_superadmin(sub, user_pool_id, region=region):
        return None, _json_response(
            403,
            {"error": "Forbidden. Superadmin access required."},
        )

    return sub, None


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


def _valid_tier(tier: str) -> bool:
    return (tier or "").upper() in ("FREE", "PRO", "BUSINESS")


def list_templates_handler(event: dict, context: dict) -> dict:
    """GET /api/admin/templates — list all platform templates (superadmin)."""
    _, err = _require_superadmin(event)
    if err:
        return err

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    resp = table.query(**query_templates())
    items = resp.get("Items", [])

    templates = []
    for item in items:
        sk = item.get("sk", "")
        if not sk.startswith("TEMPLATE#"):
            continue
        slug = sk.replace("TEMPLATE#", "")
        templates.append({
            "slug": slug,
            "name": item.get("name", slug),
            "description": item.get("description", ""),
            "tier_required": item.get("tier_required", "FREE"),
            "components": item.get("components") or {},
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        })

    templates.sort(key=lambda t: t["slug"])
    return _json_response(200, {"templates": templates})


def create_template_handler(event: dict, context: dict) -> dict:
    """POST /api/admin/templates — create template (superadmin). Body: slug, name, description, tier_required, components."""
    _, err = _require_superadmin(event)
    if err:
        return err

    body = _parse_body(event) or {}
    slug = (body.get("slug") or "").strip().lower().replace(" ", "-")
    if not slug:
        return _json_response(400, {"error": "slug is required"})

    name = (body.get("name") or slug).strip()
    description = (body.get("description") or "").strip()
    tier_required = (body.get("tier_required") or "FREE").upper()
    if not _valid_tier(tier_required):
        return _json_response(400, {"error": "tier_required must be FREE, PRO, or BUSINESS"})
    components = body.get("components")
    if components is None:
        components = {}
    if not isinstance(components, dict):
        return _json_response(400, {"error": "components must be a map"})

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Check exists
    resp = table.get_item(Key=get_template_item(slug))
    if resp.get("Item"):
        return _json_response(409, {"error": f"Template already exists: {slug}"})

    now = datetime.now(timezone.utc).isoformat()
    item = {
        "pk": pk_tenant(PLATFORM_TENANT),
        "sk": sk_template(slug),
        "slug": slug,
        "name": name,
        "description": description,
        "tier_required": tier_required,
        "components": components,
        "created_at": now,
        "updated_at": now,
    }
    table.put_item(Item=item)
    return _json_response(201, {
        "slug": slug,
        "name": name,
        "description": description,
        "tier_required": tier_required,
        "components": components,
        "created_at": now,
        "updated_at": now,
    })


def get_template_handler(event: dict, context: dict, slug: str) -> dict:
    """GET /api/admin/templates/{slug} — get template (superadmin)."""
    _, err = _require_superadmin(event)
    if err:
        return err

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    resp = table.get_item(Key=get_template_item(slug))
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": f"Template not found: {slug}"})

    return _json_response(200, {
        "slug": item.get("slug", slug),
        "name": item.get("name", slug),
        "description": item.get("description", ""),
        "tier_required": item.get("tier_required", "FREE"),
        "components": item.get("components") or {},
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    })


def update_template_handler(event: dict, context: dict, slug: str) -> dict:
    """PUT /api/admin/templates/{slug} — update template (superadmin)."""
    _, err = _require_superadmin(event)
    if err:
        return err

    body = _parse_body(event) or {}
    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    resp = table.get_item(Key=get_template_item(slug))
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": f"Template not found: {slug}"})

    updates = []
    expr_vals = {}
    expr_names = {}

    if "name" in body:
        name = (body.get("name") or "").strip() or slug
        updates.append("#n = :name")
        expr_names["#n"] = "name"
        expr_vals[":name"] = name
    if "description" in body:
        updates.append("description = :desc")
        expr_vals[":desc"] = (body.get("description") or "").strip()
    if "tier_required" in body:
        tr = (body.get("tier_required") or "FREE").upper()
        if not _valid_tier(tr):
            return _json_response(400, {"error": "tier_required must be FREE, PRO, or BUSINESS"})
        updates.append("tier_required = :tr")
        expr_vals[":tr"] = tr
    if "components" in body:
        comp = body.get("components")
        if not isinstance(comp, dict):
            return _json_response(400, {"error": "components must be a map"})
        updates.append("components = :comp")
        expr_vals[":comp"] = comp

    if not updates:
        return _json_response(400, {"error": "Provide at least one of: name, description, tier_required, components"})

    now = datetime.now(timezone.utc).isoformat()
    updates.append("updated_at = :u")
    expr_vals[":u"] = now

    kwargs = {
        "Key": get_template_item(slug),
        "UpdateExpression": "SET " + ", ".join(updates),
        "ExpressionAttributeValues": expr_vals,
    }
    if expr_names:
        kwargs["ExpressionAttributeNames"] = expr_names

    table.update_item(**kwargs)

    resp = table.get_item(Key=get_template_item(slug))
    updated = resp.get("Item", {})
    return _json_response(200, {
        "slug": updated.get("slug", slug),
        "name": updated.get("name", slug),
        "description": updated.get("description", ""),
        "tier_required": updated.get("tier_required", "FREE"),
        "components": updated.get("components") or {},
        "created_at": updated.get("created_at"),
        "updated_at": updated.get("updated_at"),
    })


def delete_template_handler(event: dict, context: dict, slug: str) -> dict:
    """DELETE /api/admin/templates/{slug} — remove template (superadmin)."""
    _, err = _require_superadmin(event)
    if err:
        return err

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    resp = table.get_item(Key=get_template_item(slug))
    if not resp.get("Item"):
        return _json_response(404, {"error": f"Template not found: {slug}"})

    table.delete_item(Key=get_template_item(slug))
    return {"statusCode": 204, "headers": {}, "body": ""}
