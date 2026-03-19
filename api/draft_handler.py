"""
Draft preview API (Task 1.116, 1.117).

GET /api/tenant/sites/{id}/draft-token — returns JWT for draft preview URL (1hr expiry).
POST /api/tenant/sites/{id}/draft-publish — renders draft HTML to S3 draft/ prefix.
"""

import json
import os
from datetime import datetime, timezone, timedelta

import boto3
import jwt

from auth_helpers import require_tenant_auth, role_can_upload
from dynamodb_helpers import get_site_item, get_template_item, pk_tenant
from middleware import with_tenant
from publish_handler import _json_response
from templates import get_renderer


def _get_jwt_secret() -> str | None:
    """Fetch JWT signing key from Secrets Manager."""
    arn = os.environ.get("JWT_SECRET_ARN")
    if not arn:
        return None
    try:
        client = boto3.client("secretsmanager")
        resp = client.get_secret_value(SecretId=arn)
        return resp.get("SecretString", "").strip() or None
    except Exception:
        return None


@with_tenant
def draft_token_handler(event: dict, context: dict) -> dict:
    """
    GET /api/tenant/sites/{id}/draft-token — issue JWT for draft preview (Task 1.117).
    Auth: admin/manager/editor. Token valid 1 hour.
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(400, {"error": "Missing tenant."})

    path = (event.get("rawPath") or event.get("path") or "").rstrip("/")
    prefix = "/api/tenant/sites/"
    suffix = "/draft-token"
    if not path.startswith(prefix) or not path.endswith(suffix):
        return _json_response(404, {"error": "Not found."})
    site_id = path[len(prefix) : -len(suffix)].strip("/")
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
        if not role_can_upload(role):
            return _json_response(403, {"error": "Editor, manager, or admin role required."})
    elif not role_can_upload(role or ""):
        return _json_response(403, {"error": "Editor, manager, or admin role required."})

    site_key = get_site_item(tenant_slug, site_id)
    site_resp = table.get_item(Key=site_key)
    site_item = site_resp.get("Item")
    if not site_item:
        return _json_response(404, {"error": "Site not found."})

    site_slug = (site_item.get("slug") or "").strip()
    if not site_slug:
        return _json_response(400, {"error": "Site has no slug."})

    secret = _get_jwt_secret()
    if not secret or secret == "REPLACE_ME":
        return _json_response(503, {"error": "Draft preview is not configured."})

    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=1)
    payload = {
        "tenant_slug": tenant_slug,
        "site_id": site_id,
        "type": "draft",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    try:
        token = jwt.encode(payload, secret, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode("utf-8")
    except Exception:
        return _json_response(500, {"error": "Failed to issue token."})

    # Return token + preview URL hint (frontend builds full URL from site slug)
    domains = (os.environ.get("DOMAINS") or "echo9.net").split(",")
    base_domain = domains[0].strip() if domains else "echo9.net"
    preview_url = f"https://{site_slug}.{base_domain}/preview?token={token}"

    return _json_response(200, {"token": token, "preview_url": preview_url, "expires_in": 3600})
