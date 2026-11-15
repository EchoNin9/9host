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

import secrets_cache
from dynamodb_helpers import get_tenant_item, pk_tenant, sk_tuser


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _get_jwt_secret() -> str | None:
    """JWT signing key from Secrets Manager (5-minute module cache, Bug #7)."""
    return secrets_cache.get_secret_string(os.environ.get("JWT_SECRET_ARN"))


# SEC-16: fixed cost-12 hash checked on miss paths (never matches; equalises timing).
_DUMMY_HASH = "$2b$12$e2OTS2cyow31VnKEVCzGbuGu8ghlpIN9cVBEzXSLXH/0BQZ9/JX8W"
# SEC-06: lock a TUSER for LOCK_SECONDS after MAX_FAILURES consecutive bad passwords.
MAX_FAILURES = 5
LOCK_SECONDS = 15 * 60


def _record_failure(table, key: dict, now_ts: int) -> None:
    """Atomically count a failed login; lock (and reset the count) once MAX_FAILURES is reached."""
    n = int(table.update_item(
        Key=key, UpdateExpression="ADD failed_logins :one", ExpressionAttributeValues={":one": 1},
        ConditionExpression="attribute_exists(pk)", ReturnValues="UPDATED_NEW",
    )["Attributes"]["failed_logins"])
    if n >= MAX_FAILURES:
        table.update_item(Key=key, UpdateExpression="SET locked_until = :t REMOVE failed_logins",
                          ExpressionAttributeValues={":t": now_ts + LOCK_SECONDS})


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

    # SEC-16: every miss path pays one bcrypt check, so response time doesn't reveal valid usernames.
    tenant = table.get_item(Key=get_tenant_item(site)).get("Item")
    tuser_key = {"pk": pk_tenant(site), "sk": sk_tuser(username)}
    item = table.get_item(Key=tuser_key).get("Item") if tenant else None
    password_hash = (item or {}).get("password_hash") or _DUMMY_HASH

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if item and int(item.get("locked_until") or 0) > now_ts:
        return _json_response(429, {"error": "Too many failed attempts. Try again later."})

    try:
        ok = bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        ok = False
    if not item or not item.get("password_hash"):
        return _json_response(401, {"error": "Invalid site or credentials."})
    if not ok:
        _record_failure(table, tuser_key, now_ts)
        return _json_response(401, {"error": "Invalid site or credentials."})
    if item.get("failed_logins") or item.get("locked_until"):
        table.update_item(Key=tuser_key, UpdateExpression="REMOVE failed_logins, locked_until")

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
        "tv": item.get("token_version"),  # SEC-04: re-checked against the TUSER row per request
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    try:
        token = jwt.encode(payload, secret, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode("utf-8")
    except Exception:
        return _json_response(500, {"error": "Failed to issue token."})

    display_name = item.get("display_name") or ""
    return _json_response(
        200,
        {"token": token, "tenant_slug": site, "role": role, "username": username, "display_name": display_name},
    )
