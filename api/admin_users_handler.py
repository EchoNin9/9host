"""
Superadmin API — global user list and stats (Task 1.48).

GET /api/admin/users — list platform admins, all users across tenants grouped by tenant, orphaned Cognito users
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
    Returns: { platform_admins: [user, ...], users_by_tenant: { tenant_slug: [user, ...] },
               orphaned: [user, ...] }
    platform_admins are Cognito superadmin-group members; they are never listed as orphaned.
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

    # Platform admins: members of the Cognito ``superadmin`` group (the group RequestContext's
    # ``cognito:groups`` check uses). Listed separately and never treated as orphaned (T-20).
    platform_admins: list[dict] = []
    orphaned: list[dict] = []
    user_pool_id = os.environ.get("USER_POOL_ID", "")
    region = os.environ.get("AWS_REGION", "us-east-1")
    if user_pool_id:
        client = boto3.client("cognito-idp", region_name=region)
        superadmin_subs = _superadmin_users(client, user_pool_id, platform_admins)

        orphan_candidates: list[dict] = []
        try:
            paginator = client.get_paginator("list_users")
            for page in paginator.paginate(UserPoolId=user_pool_id):
                for u in page.get("Users", []):
                    sub, attrs = _cognito_identity(u)
                    if sub and sub not in cognito_subs_in_db:
                        orphan_candidates.append({
                            "type": "cognito",
                            "sub": sub,
                            "username": u.get("Username") or sub,
                            "email": attrs.get("email", ""),
                            "name": attrs.get("name", ""),
                            "role": None,
                        })
        except Exception:  # noqa: BLE001
            pass

        if superadmin_subs is None:
            # ListUsersInGroup unavailable (e.g. IAM not yet granted): fall back to per-candidate
            # group lookups, limited to the (few) users without a tenant profile.
            superadmin_subs = set()
            for cand in orphan_candidates:
                if _user_in_superadmin_group(client, user_pool_id, cand["username"]):
                    superadmin_subs.add(cand["sub"])
                    platform_admins.append(_platform_admin(cand["sub"], cand["email"], cand["name"]))

        for cand in orphan_candidates:
            if cand["sub"] not in superadmin_subs:
                cand.pop("username", None)
                orphaned.append(cand)

        # Flag platform admins who also hold tenant memberships.
        for users in users_by_tenant.values():
            for user in users:
                if user.get("type") == "cognito" and user.get("sub") in superadmin_subs:
                    user["is_superadmin"] = True

    return _json_response(200, {
        "platform_admins": platform_admins,
        "users_by_tenant": users_by_tenant,
        "orphaned": orphaned,
    })


SUPERADMIN_GROUP = "superadmin"  # infra/cognito.tf aws_cognito_user_group.superadmin


def _cognito_identity(u: dict) -> tuple[str, dict]:
    attrs = {a.get("Name"): a.get("Value") for a in u.get("Attributes", [])}
    return attrs.get("sub") or u.get("Username") or "", attrs


def _platform_admin(sub: str, email: str, name: str) -> dict:
    return {
        "type": "cognito",
        "sub": sub,
        "email": email,
        "name": name,
        "role": SUPERADMIN_GROUP,
        "is_superadmin": True,
    }


def _superadmin_users(client, user_pool_id: str, out: list[dict]) -> set[str] | None:
    """Members of the superadmin group via ListUsersInGroup (paginated). None if the call fails."""
    found: list[dict] = []
    try:
        paginator = client.get_paginator("list_users_in_group")
        for page in paginator.paginate(UserPoolId=user_pool_id, GroupName=SUPERADMIN_GROUP):
            for u in page.get("Users", []):
                sub, attrs = _cognito_identity(u)
                if sub:
                    found.append(_platform_admin(sub, attrs.get("email", ""), attrs.get("name", "")))
    except Exception:  # noqa: BLE001
        return None
    out.extend(found)
    return {u["sub"] for u in found}


def _user_in_superadmin_group(client, user_pool_id: str, username: str) -> bool:
    try:
        resp = client.admin_list_groups_for_user(UserPoolId=user_pool_id, Username=username)
    except Exception:  # noqa: BLE001
        return False
    return any((g.get("GroupName") or "").lower() == SUPERADMIN_GROUP for g in resp.get("Groups", []))


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
