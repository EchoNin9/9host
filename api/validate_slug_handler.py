"""
GET /api/validate-slug — check if a site slug is available (Task 1.77).

Query param: slug (required)
Query param: exclude_site_id (optional) — when editing, exclude current site from check.

Requires tenant context (X-Tenant-Slug) and auth.
"""

import json
import os
import boto3

from auth_helpers import require_tenant_auth
from dynamodb_helpers import slug_is_taken
from middleware import with_tenant


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


@with_tenant
def validate_slug_handler(event: dict, context: dict) -> dict:
    """GET /api/validate-slug?slug={slug}&exclude_site_id={id}"""
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(
            400,
            {"error": "Missing tenant. Use subdomain or X-Tenant-Slug header."},
        )

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    # Parse query params (API Gateway v2: flat dict)
    params = event.get("queryStringParameters") or {}
    slug = params.get("slug") or ""
    if isinstance(slug, list):
        slug = slug[0] if slug else ""
    exclude_site_id = params.get("exclude_site_id")
    if isinstance(exclude_site_id, list):
        exclude_site_id = exclude_site_id[0] if exclude_site_id else None

    if not slug or not slug.strip():
        return _json_response(400, {"error": "slug query param is required."})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    region = os.environ.get("AWS_REGION", "us-east-1")
    auth_result = require_tenant_auth(event, table, tenant_slug, region)
    if auth_result[0] is not True:
        _, err_resp = auth_result
        return _json_response(
            err_resp.get("statusCode", 401),
            json.loads(err_resp.get("body", "{}")),
        )

    taken = slug_is_taken(table, slug, exclude_site_id=exclude_site_id or None)
    return _json_response(200, {"available": not taken, "slug": slug.strip().lower()})
