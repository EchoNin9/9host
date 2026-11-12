"""
Superadmin API — global user list and stats (Task 1.48).

GET /api/admin/users — list all users across tenants, grouped by tenant, orphaned Cognito users
GET /api/admin/stats — platform stats: total_users, total_tenants, etc.
"""

import json
import os

import boto3

from dynamodb_helpers import query_all_users_by_entity
from request_context import RequestContext
from tenant_store import DynamoDBTenantStore


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _query_all_users(table) -> list[dict]:
    """All USER#/TUSER# items across tenants via GSI byEntity (superadmin bypass; no scan)."""
    params = query_all_users_by_entity()
    resp = table.query(**params)
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        resp = table.query(**params, ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return items


def admin_users_handler(ctx: RequestContext) -> dict:
    """
    GET /api/admin/users — list all users across tenants.
    Returns: { users_by_tenant: { tenant_slug: [user, ...] }, orphaned: [user, ...] }
    """
    ctx.require_superadmin()

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    users_by_tenant = {}
    cognito_subs_in_db = set()

    items = _query_all_users(table)

    for item in items:
        pk = item.get("pk", "")
        sk = item.get("sk", "")
        if not pk.startswith("TENANT#"):
            continue

        tenant_slug = pk.replace("TENANT#", "")
        if not tenant_slug:
            continue

        if sk.startswith("TUSER#"):
            username = sk.replace("TUSER#", "")
            user_obj = {
                "type": "tenant_user",
                "username": username,
                "display_name": item.get("display_name", ""),
                "email": None,
                "role": item.get("role", "member"),
            }
        elif sk.endswith("#PROFILE"):
            sub = item.get("sub", "")
            cognito_subs_in_db.add(sub)
            user_obj = {
                "type": "cognito",
                "sub": sub,
                "email": item.get("email", ""),
                "name": item.get("name", ""),
                "role": item.get("role", "member"),
            }
        else:
            continue

        if tenant_slug not in users_by_tenant:
            users_by_tenant[tenant_slug] = []
        users_by_tenant[tenant_slug].append(user_obj)

    # Orphaned: Cognito users with no tenant profile (optional, can be expensive)
    orphaned = []
    user_pool_id = os.environ.get("USER_POOL_ID", "")
    region = os.environ.get("AWS_REGION", "us-east-1")
    if user_pool_id:
        try:
            client = boto3.client("cognito-idp", region_name=region)
            paginator = client.get_paginator("list_users")
            for page in paginator.paginate(UserPoolId=user_pool_id):
                for u in page.get("Users", []):
                    sub = u.get("Username") or ""
                    attrs = {a.get("Name"): a.get("Value") for a in u.get("Attributes", [])}
                    if attrs.get("sub"):
                        sub = attrs["sub"]
                    if sub and sub not in cognito_subs_in_db:
                        orphaned.append({
                            "type": "cognito",
                            "sub": sub,
                            "email": attrs.get("email", ""),
                            "name": attrs.get("name", ""),
                            "role": None,
                        })
        except Exception:
            pass

    return _json_response(200, {
        "users_by_tenant": users_by_tenant,
        "orphaned": orphaned,
    })


def admin_stats_handler(ctx: RequestContext) -> dict:
    """
    GET /api/admin/stats — platform stats.
    Returns: { total_users, total_tenants, total_cognito_users, total_tenant_users }
    """
    ctx.require_superadmin()

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Count tenants via the byEntity GSI (ENTITY#TENANT); superadmin cross-tenant bypass, no Scan (T-17).
    total_tenants = len(DynamoDBTenantStore(table).list_all_tenants())

    # Count users (USER# and TUSER#)
    total_cognito = 0
    total_tenant_users = 0
    for item in _query_all_users(table):
        if item.get("sk", "").startswith("TUSER#"):
            total_tenant_users += 1
        elif item.get("sk", "").endswith("#PROFILE"):
            total_cognito += 1

    total_users = total_cognito + total_tenant_users

    return _json_response(200, {
        "total_users": total_users,
        "total_tenants": total_tenants,
        "total_cognito_users": total_cognito,
        "total_tenant_users": total_tenant_users,
    })
