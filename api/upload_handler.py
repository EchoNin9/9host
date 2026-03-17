"""
Upload pre-signed POST (Task 1.89).

POST /api/tenant/sites/{site_id}/upload-url — returns S3 presigned POST URL
with content-length-range condition (10 MB per file). Enforces per-upload size limit.
"""

import json
import os
import re
import uuid

import boto3

from auth_helpers import require_tenant_auth, role_can_upload
from dynamodb_helpers import get_site_item, get_tenant_item
from middleware import with_tenant
from tier_config import upload_limit_bytes


S3_MEDIA_BUCKET = "9host-media"
# Sanitize: replace unsafe chars with underscore. Block path traversal.
FILENAME_UNSAFE = re.compile(r"[^a-zA-Z0-9._-]|[.]{2,}|[/\\]")


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _parse_body(event: dict) -> dict | None:
    body = event.get("body")
    if not body:
        return None
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None
    return body


@with_tenant
def upload_url_handler(event: dict, context: dict) -> dict:
    """
    POST /api/tenant/sites/{site_id}/upload-url
    Body: { "content_length": number, "filename": string }
    Returns: { "url": string, "method": "POST", "fields": {...}, "key": string }
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(400, {"error": "Missing tenant. Use subdomain or X-Tenant-Slug header."})

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    prefix = "/api/tenant/sites/"
    if not path.startswith(prefix):
        return _json_response(404, {"error": "Not found."})
    rest = path[len(prefix) :].strip("/")
    parts = rest.split("/")
    if len(parts) < 2 or parts[1] != "upload-url":
        return _json_response(404, {"error": "Not found."})
    site_id = parts[0]
    if not site_id:
        return _json_response(400, {"error": "Missing site_id."})

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
        from auth_helpers import get_user_role_in_tenant

        role_in_tenant = get_user_role_in_tenant(table, sub_or_username, tenant_slug)
        if not role_can_upload(role_in_tenant or ""):
            return _json_response(403, {"error": "Admin, manager, or editor role required to upload."})
    elif not role_can_upload(role):
        return _json_response(403, {"error": "Admin, manager, or editor role required to upload."})

    site_key = get_site_item(tenant_slug, site_id)
    site_resp = table.get_item(Key=site_key)
    if not site_resp.get("Item"):
        return _json_response(404, {"error": "Site not found."})

    tenant_item = table.get_item(Key=get_tenant_item(tenant_slug)).get("Item")
    tier = (tenant_item.get("tier") or "FREE").upper()
    limit = upload_limit_bytes(tier)

    body = _parse_body(event)
    if not body:
        return _json_response(400, {"error": "JSON body required."})

    content_length = body.get("content_length")
    if content_length is None:
        return _json_response(400, {"error": "content_length required."})
    try:
        content_length = int(content_length)
    except (TypeError, ValueError):
        return _json_response(400, {"error": "content_length must be a number."})
    if content_length < 0:
        return _json_response(400, {"error": "content_length must be non-negative."})
    if content_length > limit:
        return _json_response(400, {"error": f"File too large. Max {limit} bytes ({limit // (1024*1024)} MB) per upload."})

    filename = (body.get("filename") or "").strip()
    if not filename:
        return _json_response(400, {"error": "filename required."})
    # Sanitize: "My Photo.png" -> "My_Photo.png", block path traversal
    safe_name = FILENAME_UNSAFE.sub("_", filename)
    safe_name = re.sub(r"_+", "_", safe_name).strip("_")  # collapse multiple _, trim
    if not safe_name:
        safe_name = "upload"
    # Preserve extension if present
    if "." in safe_name and not safe_name.startswith("."):
        base, ext = safe_name.rsplit(".", 1)
        if ext and len(ext) <= 6 and ext.isalnum():
            safe_name = f"{base or 'upload'}.{ext.lower()}"

    unique = str(uuid.uuid4())[:8]
    key = f"{tenant_slug}/{site_id}/{unique}-{safe_name}"

    s3 = boto3.client("s3", region_name=region)
    presigned = s3.generate_presigned_post(
        Bucket=S3_MEDIA_BUCKET,
        Key=key,
        Conditions=[
            ["content-length-range", 0, limit],
        ],
        ExpiresIn=3600,
    )

    return _json_response(200, {
        "url": presigned["url"],
        "method": "POST",
        "fields": presigned["fields"],
        "key": key,
    })
