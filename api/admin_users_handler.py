"""
Superadmin API — global user list and stats (Task 1.48).

GET /api/admin/users — list all users across tenants, grouped by tenant, orphaned Cognito users
GET /api/admin/stats — platform stats: total_users, total_tenants, etc.
"""

import json
import os

import boto3

from auth_helpers import get_sub_from_access_token, is_superadmin
from dynamodb_helpers import query_all_users_by_entity


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


def admin_users_handler(event: dict, context: dict) -> dict:
    """
    GET /api/admin/users — list all users across tenants.
    Returns: { users_by_tenant: { tenant_slug: [user, ...] }, orphaned: [user, ...] }
    """
    _, err = _require_superadmin(event)
    if err:
        return err

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    users_by_tenant = {}
    cognito_subs_in_db = set()

    # Try GSI byEntity first; fallback to scan
    try:
        params = query_all_users_by_entity()
        resp = table.query(**params)
        items = resp.get("Items", [])
        while "LastEvaluatedKey" in resp:
            params["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            resp = table.query(**params)
            items.extend(resp.get("Items", []))
    except Exception:
        # Fallback: scan for USER# and TUSER# items
        resp = table.scan(
            FilterExpression="begins_with(pk, :pk) AND (begins_with(sk, :u) OR begins_with(sk, :tu))",
            ExpressionAttributeValues={
                ":pk": "TENANT#",
                ":u": "USER#",
                ":tu": "TUSER#",
            },
        )
        items = resp.get("Items", [])
        while "LastEvaluatedKey" in resp:
            resp = table.scan(
                FilterExpression="begins_with(pk, :pk) AND (begins_with(sk, :u) OR begins_with(sk, :tu))",
                ExpressionAttributeValues={
                    ":pk": "TENANT#",
                    ":u": "USER#",
                    ":tu": "TUSER#",
                },
                ExclusiveStartKey=resp["LastEvaluatedKey"],
            )
            items.extend(resp.get("Items", []))

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


def admin_stats_handler(event: dict, context: dict) -> dict:
    """
    GET /api/admin/stats — platform stats.
    Returns: { total_users, total_tenants, total_cognito_users, total_tenant_users }
    """
    _, err = _require_superadmin(event)
    if err:
        return err

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    # Count tenants
    tenant_resp = table.scan(
        FilterExpression="begins_with(pk, :pk) AND sk = :sk",
        ExpressionAttributeValues={":pk": "TENANT#", ":sk": "TENANT"},
    )
    total_tenants = len(tenant_resp.get("Items", []))
    while "LastEvaluatedKey" in tenant_resp:
        tenant_resp = table.scan(
            FilterExpression="begins_with(pk, :pk) AND sk = :sk",
            ExpressionAttributeValues={":pk": "TENANT#", ":sk": "TENANT"},
            ExclusiveStartKey=tenant_resp["LastEvaluatedKey"],
        )
        total_tenants += len(tenant_resp.get("Items", []))

    # Count users (USER# and TUSER#)
    total_cognito = 0
    total_tenant_users = 0
    try:
        params = query_all_users_by_entity()
        resp = table.query(**params)
        for item in resp.get("Items", []):
            if item.get("sk", "").startswith("TUSER#"):
                total_tenant_users += 1
            elif item.get("sk", "").endswith("#PROFILE"):
                total_cognito += 1
        while "LastEvaluatedKey" in resp:
            params["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
            resp = table.query(**params)
            for item in resp.get("Items", []):
                if item.get("sk", "").startswith("TUSER#"):
                    total_tenant_users += 1
                elif item.get("sk", "").endswith("#PROFILE"):
                    total_cognito += 1
    except Exception:
        resp = table.scan(
            FilterExpression="begins_with(pk, :pk) AND (begins_with(sk, :u) OR begins_with(sk, :tu))",
            ExpressionAttributeValues={
                ":pk": "TENANT#",
                ":u": "USER#",
                ":tu": "TUSER#",
            },
        )
        for item in resp.get("Items", []):
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
