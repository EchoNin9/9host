"""
Site login handler — non-Cognito tenant user auth (Task 1.44).

POST /api/auth/site-login — authenticate by username + password + site (tenant_slug).
Returns custom JWT for API access. No Cognito required.
"""

import json
import os
import re
from datetime import datetime, timezone, timedelta

import bcrypt
import boto3
import jwt

from dynamodb_helpers import get_tenant_item, pk_tenant, sk_tuser


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


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


USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$")


def site_login_handler(event: dict, context: dict) -> dict:
    """
    POST /api/auth/site-login — authenticate non-Cognito tenant user.

    Body: { "username": str, "password": str, "site": str }
    site = tenant_slug (e.g. acme-corp)

    Returns: { "token": str, "tenant_slug": str, "role": str }
    """
    if event.get("requestContext", {}).get("http", {}).get("method") != "POST":
        return _json_response(405, {"error": "Method not allowed."})

    body = event.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body) if body else {}
        except json.JSONDecodeError:
            body = {}
    elif not body:
        body = {}

    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    site = (body.get("site") or "").strip().lower()

    if not username:
        return _json_response(400, {"error": "username is required."})
    if not password:
        return _json_response(400, {"error": "password is required."})
    if not site:
        return _json_response(400, {"error": "site is required."})

    if not USERNAME_PATTERN.match(username):
        return _json_response(400, {"error": "username must be alphanumeric, dots, underscores, hyphens."})

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Validate tenant exists
    tenant_key = get_tenant_item(site)
    tenant = table.get_item(Key=tenant_key).get("Item")
    if not tenant:
        return _json_response(401, {"error": "Invalid site or credentials."})

    # Look up TUSER
    tuser_key = {"pk": pk_tenant(site), "sk": sk_tuser(username)}
    item = table.get_item(Key=tuser_key).get("Item")
    if not item:
        return _json_response(401, {"error": "Invalid site or credentials."})

    password_hash = item.get("password_hash", "")
    if not password_hash:
        return _json_response(401, {"error": "Invalid site or credentials."})

    try:
        if not bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")):
            return _json_response(401, {"error": "Invalid site or credentials."})
    except Exception:
        return _json_response(401, {"error": "Invalid site or credentials."})

    role = item.get("role", "member")

    secret = _get_jwt_secret()
    if not secret or secret == "REPLACE_ME":
        return _json_response(503, {"error": "Site login is not configured."})

    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=24)
    payload = {
        "username": username,
        "tenant_slug": site,
        "role": role,
        "user_type": "tenant_user",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    try:
        token = jwt.encode(payload, secret, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode("utf-8")
    except Exception:
        return _json_response(500, {"error": "Failed to issue token."})

    return _json_response(200, {"token": token, "tenant_slug": site, "role": role})
