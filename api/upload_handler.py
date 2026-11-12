"""
Upload pre-signed POST (Task 1.89).

POST /api/tenant/sites/{site_id}/upload-url — S3 presigned POST with a content-length-range
condition (per-tier per-file limit). Admin/manager/editor or a custom
role with the 'sites' permission (T-15).
"""

import os
import re
import uuid

import boto3

from request_context import RequestContext, respond
from tenant_store import DynamoDBTenantStore
from tier_config import upload_limit_bytes

S3_MEDIA_BUCKET = "9host-media"
UPLOAD_ROLES = ("admin", "manager", "editor")
# Sanitize: replace unsafe chars with underscore. Block path traversal.
FILENAME_UNSAFE = re.compile(r"[^a-zA-Z0-9._-]|[.]{2,}|[/\\]")


def _safe_filename(filename: str) -> str:
    """"My Photo.png" -> "My_Photo.png"; blocks path traversal; keeps a short alnum extension."""
    safe = re.sub(r"_+", "_", FILENAME_UNSAFE.sub("_", filename)).strip("_") or "upload"
    if "." in safe and not safe.startswith("."):
        base, ext = safe.rsplit(".", 1)
        if ext and len(ext) <= 6 and ext.isalnum():
            safe = f"{base or 'upload'}.{ext.lower()}"
    return safe


def upload_url_handler(ctx: RequestContext) -> dict:
    """Body: {"content_length": number, "filename": string} -> {"url", "method", "fields", "key"}."""
    tenant_slug, _ = ctx.require_tenant_member()
    parts = [p for p in ctx.path[len("/api/tenant/sites/"):].split("/") if p]
    if len(parts) != 2 or parts[1] != "upload-url":
        return respond(404, {"error": "Not found."})
    site_id = parts[0]
    ctx.require_permission("sites", UPLOAD_ROLES)

    store = DynamoDBTenantStore()
    if not store.get_site(tenant_slug, site_id):
        return respond(404, {"error": "Site not found."})
    limit = upload_limit_bytes(((store.get_tenant(tenant_slug) or {}).get("tier") or "FREE").upper())

    body = ctx.json_body()
    if not body:
        return respond(400, {"error": "JSON body required."})
    content_length = body.get("content_length")
    if content_length is None:
        return respond(400, {"error": "content_length required."})
    try:
        content_length = int(content_length)
    except (TypeError, ValueError):
        return respond(400, {"error": "content_length must be a number."})
    if content_length < 0:
        return respond(400, {"error": "content_length must be non-negative."})
    if content_length > limit:
        return respond(400, {"error": f"File too large. Max {limit} bytes ({limit // (1024*1024)} MB) per upload."})
    filename = (body.get("filename") or "").strip()
    if not filename:
        return respond(400, {"error": "filename required."})

    key = f"{tenant_slug}/{site_id}/{str(uuid.uuid4())[:8]}-{_safe_filename(filename)}"
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    presigned = s3.generate_presigned_post(
        Bucket=S3_MEDIA_BUCKET, Key=key, Conditions=[["content-length-range", 0, limit]], ExpiresIn=3600,
    )
    return respond(200, {"url": presigned["url"], "method": "POST", "fields": presigned["fields"], "key": key})
