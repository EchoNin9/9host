"""
GET /api/validate-slug — check if a site slug is available (Task 1.77).

Query param: slug (required)
Query param: exclude_site_id (optional) — when editing, exclude current site from check.

Requires tenant context (X-Tenant-Slug) and auth.
"""

import json

from dynamodb_helpers import slug_is_taken
from request_context import RequestContext
from tenant_store import DynamoDBTenantStore


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def validate_slug_handler(ctx: RequestContext) -> dict:
    """GET /api/validate-slug?slug={slug}&exclude_site_id={id}"""
    ctx.require_tenant_member()

    # Parse query params (API Gateway v2: flat dict)
    params = ctx.event.get("queryStringParameters") or {}
    slug = params.get("slug") or ""
    if isinstance(slug, list):
        slug = slug[0] if slug else ""
    exclude_site_id = params.get("exclude_site_id")
    if isinstance(exclude_site_id, list):
        exclude_site_id = exclude_site_id[0] if exclude_site_id else None

    if not slug or not slug.strip():
        return _json_response(400, {"error": "slug query param is required."})

    taken = slug_is_taken(DynamoDBTenantStore().table, slug, exclude_site_id=exclude_site_id or None)
    return _json_response(200, {"available": not taken, "slug": slug.strip().lower()})
