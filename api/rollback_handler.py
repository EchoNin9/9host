"""
Site rollback API (Task 1.96b).

POST /api/tenant/sites/{id}/rollback?version=N — validate version exists,
copy v{N} to current/, update current.json, update Site. Admin/manager only.
"""

import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError as BotoClientError

from auth_helpers import require_tenant_admin_or_manager, require_tenant_auth, role_is_admin_or_manager
from dynamodb_helpers import get_site_item, pk_tenant
from middleware import with_tenant

S3_SITES_BUCKET = "9host-sites"
HTML_CACHE_CONTROL = "max-age=60, s-maxage=300"
ASSET_CACHE_CONTROL = "max-age=31536000, immutable"


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _rollback_site(
    table,
    s3_client,
    tenant_slug: str,
    site_id: str,
    version: int,
) -> dict:
    """Rollback to version N: copy v{N} to current/, update current.json, update Site."""
    base = f"{tenant_slug}/{site_id}"
    v_prefix = f"{base}/published/v{version}/"
    current_prefix = f"{base}/published/current/"
    manifest_key = f"{v_prefix}manifest.json"

    # Validate version exists
    try:
        obj = s3_client.get_object(Bucket=S3_SITES_BUCKET, Key=manifest_key)
        manifest = json.loads(obj["Body"].read().decode())
    except BotoClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchKey":
            return None  # Version not found
        raise

    files = manifest.get("files", [])
    if not files:
        return None

    # Copy each file from v{N}/ to current/
    for entry in files:
        path = entry.get("path", "")
        if not path:
            continue
        key_v = f"{v_prefix}{path}"
        key_current = f"{current_prefix}{path}"
        is_html = path.endswith(".html")
        cache = HTML_CACHE_CONTROL if is_html else ASSET_CACHE_CONTROL
        s3_client.copy_object(
            Bucket=S3_SITES_BUCKET,
            CopySource={"Bucket": S3_SITES_BUCKET, "Key": key_v},
            Key=key_current,
            CacheControl=cache,
        )

    now = datetime.now(timezone.utc).isoformat()
    current_data = {
        "version": version,
        "published_at": manifest.get("published_at", now),
        "manifest": f"v{version}/manifest.json",
    }
    current_key = f"{base}/published/current.json"
    s3_client.put_object(
        Bucket=S3_SITES_BUCKET,
        Key=current_key,
        Body=json.dumps(current_data),
        ContentType="application/json",
    )

    # Update Site record
    site_key = get_site_item(tenant_slug, site_id)
    table.update_item(
        Key=site_key,
        UpdateExpression="SET published_version = :ver, updated_at = :now",
        ExpressionAttributeValues={":ver": version, ":now": now},
    )

    return {
        "version": version,
        "rolled_back_at": now,
    }


@with_tenant
def rollback_handler(event: dict, context: dict) -> dict:
    """
    POST /api/tenant/sites/{id}/rollback?version=N — rollback to version (Task 1.96b).
    Admin/manager only.
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(400, {"error": "Missing tenant. Use subdomain or X-Tenant-Slug header."})

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    prefix = "/api/tenant/sites/"
    if not path.startswith(prefix) or "/rollback" not in path:
        return _json_response(404, {"error": "Not found."})

    rest = path[len(prefix) :].strip("/")
    parts = rest.split("/")
    if len(parts) != 2 or parts[1] != "rollback":
        return _json_response(404, {"error": "Not found."})
    site_id = parts[0]
    if not site_id:
        return _json_response(400, {"error": "Missing site_id."})

    query = event.get("queryStringParameters") or {}
    version_str = (query.get("version") or "").strip()
    if not version_str or not version_str.isdigit():
        return _json_response(400, {"error": "Query parameter version=N is required (integer)."})
    version = int(version_str)
    if version < 1:
        return _json_response(400, {"error": "Version must be >= 1."})

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    region = os.environ.get("AWS_REGION", "us-east-1")
    s3_client = boto3.client("s3", region_name=region)

    auth_result = require_tenant_auth(event, table, tenant_slug, region)
    if auth_result[0] is not True:
        _, err_resp = auth_result
        return _json_response(err_resp.get("statusCode", 401), json.loads(err_resp.get("body", "{}")))
    _, sub_or_username, role, is_cognito = auth_result

    if is_cognito:
        ok, err = require_tenant_admin_or_manager(table, sub_or_username, tenant_slug, event)
        if not ok:
            return _json_response(403, {"error": err or "Forbidden."})
    elif not role_is_admin_or_manager(role):
        return _json_response(403, {"error": "Admin or manager role required."})

    site_key = get_site_item(tenant_slug, site_id)
    site_resp = table.get_item(Key=site_key)
    site_item = site_resp.get("Item")
    if not site_item:
        return _json_response(404, {"error": "Site not found."})

    try:
        result = _rollback_site(table, s3_client, tenant_slug, site_id, version)
        if result is None:
            return _json_response(404, {"error": f"Version {version} not found. No published v{version}."})
        return _json_response(200, {"rollback": result})
    except BotoClientError as e:
        return _json_response(500, {"error": "Rollback failed.", "detail": str(e)})
