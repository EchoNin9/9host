"""
Superadmin API — admin-scoped tenant sub-resources (Tasks 1.36–1.40).

DELETE /api/admin/tenants/{slug} — cascade delete tenant
GET/POST/DELETE /api/admin/tenants/{slug}/domains — admin domains CRUD
GET/POST/PUT/DELETE /api/admin/tenants/{slug}/sites — admin sites CRUD
GET/POST/PUT/DELETE /api/admin/tenants/{slug}/users — admin users CRUD
PUT /api/admin/tenants/{slug}/settings — update tenant settings

All require superadmin. Bypass membership/tier checks.
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import unquote

import bcrypt
import boto3

from auth_helpers import get_sub_from_access_token, is_superadmin
from dynamodb_helpers import (
    get_domain_item,
    get_role_item,
    get_site_item,
    get_tenant_item,
    get_tuser_item,
    get_user_permissions_item,
    get_user_profile_item,
    gsi1pk_user,
    gsi1sk_tenant_profile,
    gsi3pk_entity_user,
    gsi3sk_tuser,
    gsi3sk_user,
    get_template_item,
    pk_tenant,
    query_domains_in_tenant,
    query_roles_in_tenant,
    query_sites_in_tenant,
    query_users_in_tenant,
    sk_domain,
    sk_site,
    sk_tuser,
    sk_user_permissions,
    sk_user_profile,
)

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]$|^[a-zA-Z0-9]$")


def _json_response(status: int, body: dict, empty_body: bool = False) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": "" if empty_body else json.dumps(body),
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


def _get_table():
    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return None, _json_response(500, {"error": "DYNAMODB_TABLE not configured"})
    return boto3.resource("dynamodb").Table(table_name), None


def _get_email_from_cognito_sub(sub: str, region: str) -> str:
    """Resolve Cognito sub to email via AdminGetUser (Task 1.50)."""
    if not sub:
        return ""
    try:
        client = boto3.client("cognito-idp", region_name=region)
        resp = client.admin_get_user(
            UserPoolId=os.environ.get("USER_POOL_ID", ""),
            Username=sub,
        )
        for attr in resp.get("UserAttributes", []):
            if attr.get("Name") == "email":
                return attr.get("Value", "")
    except Exception:
        pass
    return ""


# --- Task 1.36: DELETE /api/admin/tenants/{slug} (cascade) ---

def delete_tenant_handler(event: dict, context: dict, tenant_slug: str) -> dict:
    """
    DELETE /api/admin/tenants/{slug} — cascade delete tenant and all sub-resources.
    Deletes: sites, domains, user profiles, user permissions, tenant.
    """
    _, err = _require_superadmin(event)
    if err:
        return err

    table, err = _get_table()
    if err:
        return err

    # Verify tenant exists
    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    if not resp.get("Item"):
        return _json_response(404, {"error": f"Tenant not found: {tenant_slug}"})

    # Query all items in tenant partition
    pk = pk_tenant(tenant_slug)
    items = []
    params = {
        "KeyConditionExpression": "pk = :pk",
        "ExpressionAttributeValues": {":pk": pk},
    }
    while True:
        resp = table.query(**params)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        params["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    # Batch delete (DynamoDB limit 25 per batch_write_item)
    for i in range(0, len(items), 25):
        batch = items[i : i + 25]
        table.meta.client.batch_write_item(
            RequestItems={
                table.name: [
                    {"DeleteRequest": {"Key": {"pk": it["pk"], "sk": it["sk"]}}}
                    for it in batch
                ]
            }
        )

    return _json_response(204, {}, empty_body=True)


# --- Task 1.37: CRUD /api/admin/tenants/{slug}/domains ---

DOMAIN_PATTERN = re.compile(
    r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$",
    re.IGNORECASE,
)


def _domain_to_response(item: dict) -> dict:
    sk = item.get("sk", "")
    domain = sk.replace("DOMAIN#", "") if sk.startswith("DOMAIN#") else ""
    return {
        "domain": domain,
        "site_id": item.get("site_id", ""),
        "status": item.get("status", "pending"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def admin_domains_handler(event: dict, context: dict, tenant_slug: str, path_suffix: str) -> dict:
    """GET/POST /api/admin/tenants/{slug}/domains, GET/DELETE /api/admin/tenants/{slug}/domains/{domain}."""
    _, err = _require_superadmin(event)
    if err:
        return err

    table, err = _get_table()
    if err:
        return err

    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    if not resp.get("Item"):
        return _json_response(404, {"error": f"Tenant not found: {tenant_slug}"})

    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    )

    # path_suffix is "domains" or "domains/example.com"
    parts = path_suffix.strip("/").split("/")
    domain = parts[1] if len(parts) > 1 else None
    domain = unquote(domain).lower() if domain else None

    if method == "GET" and not domain:
        params = query_domains_in_tenant(tenant_slug)
        resp = table.query(**params)
        domains = [_domain_to_response(it) for it in resp.get("Items", [])]
        return _json_response(200, {"domains": domains})

    if method == "GET" and domain:
        key = get_domain_item(tenant_slug, domain)
        resp = table.get_item(Key=key)
        if not resp.get("Item"):
            return _json_response(404, {"error": "Domain not found."})
        return _json_response(200, {"domain": _domain_to_response(resp["Item"])})

    if method == "POST" and not domain:
        body = _parse_body(event) or {}
        domain_raw = (body.get("domain") or "").strip().lower()
        site_id = (body.get("site_id") or "").strip()
        status = (body.get("status") or "pending").strip().lower()

        if not domain_raw:
            return _json_response(400, {"error": "domain is required."})
        if not site_id:
            return _json_response(400, {"error": "site_id is required."})
        if status not in ("pending", "verified"):
            status = "pending"
        if not DOMAIN_PATTERN.match(domain_raw):
            return _json_response(400, {"error": "domain must be valid (e.g. example.com)."})

        site_resp = table.get_item(Key=get_site_item(tenant_slug, site_id))
        if not site_resp.get("Item"):
            return _json_response(404, {"error": "Site not found."})

        key = get_domain_item(tenant_slug, domain_raw)
        if table.get_item(Key=key).get("Item"):
            return _json_response(409, {"error": "Domain already exists for this tenant."})

        now = datetime.now(timezone.utc).isoformat()
        item = {
            "pk": pk_tenant(tenant_slug),
            "sk": sk_domain(domain_raw),
            "gsi2pk": f"DOMAIN#{domain_raw}",
            "gsi2sk": f"TENANT#{tenant_slug}",
            "site_id": site_id,
            "status": status,
            "created_at": now,
            "updated_at": now,
        }
        table.put_item(Item=item)
        return _json_response(201, {"domain": _domain_to_response(item)})

    if method == "DELETE" and domain:
        key = get_domain_item(tenant_slug, domain)
        if not table.get_item(Key=key).get("Item"):
            return _json_response(404, {"error": "Domain not found."})
        table.delete_item(Key=key)
        return _json_response(204, {}, empty_body=True)

    return _json_response(405, {"error": "Method not allowed."})


# --- Task 1.38: CRUD /api/admin/tenants/{slug}/sites ---

SITE_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


def _site_to_response(item: dict) -> dict:
    sk = item.get("sk", "")
    site_id = sk.replace("SITE#", "") if sk.startswith("SITE#") else ""
    return {
        "id": site_id,
        "name": item.get("name", ""),
        "slug": item.get("slug", ""),
        "status": item.get("status", "draft"),
        "template_id": item.get("template_id"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def _tier_rank(tier: str) -> int:
    t = (tier or "FREE").upper()
    if t == "FREE":
        return 0
    if t == "PRO":
        return 1
    if t == "BUSINESS":
        return 2
    return 0


def admin_sites_handler(event: dict, context: dict, tenant_slug: str, path_suffix: str) -> dict:
    """GET/POST /api/admin/tenants/{slug}/sites, GET/PUT/DELETE /api/admin/tenants/{slug}/sites/{id}."""
    _, err = _require_superadmin(event)
    if err:
        return err

    table, err = _get_table()
    if err:
        return err

    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    if not resp.get("Item"):
        return _json_response(404, {"error": f"Tenant not found: {tenant_slug}"})

    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    )

    parts = path_suffix.strip("/").split("/")
    site_id = parts[1] if len(parts) > 1 else None

    if method == "GET" and not site_id:
        params = query_sites_in_tenant(tenant_slug)
        resp = table.query(**params)
        sites = [_site_to_response(it) for it in resp.get("Items", [])]
        return _json_response(200, {"sites": sites})

    if method == "GET" and site_id:
        key = get_site_item(tenant_slug, site_id)
        resp = table.get_item(Key=key)
        if not resp.get("Item"):
            return _json_response(404, {"error": "Site not found."})
        return _json_response(200, {"site": _site_to_response(resp["Item"])})

    if method == "POST" and not site_id:
        body = _parse_body(event) or {}
        name = (body.get("name") or "").strip()
        slug = (body.get("slug") or "").strip().lower()
        status = (body.get("status") or "draft").strip().lower()
        template_id = (body.get("template_id") or "").strip().lower() or None

        if not name:
            return _json_response(400, {"error": "name is required."})
        if status not in ("draft", "published"):
            status = "draft"
        if not slug:
            slug = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))
            if not slug:
                slug = str(uuid.uuid4())[:8]
        if not SITE_SLUG_PATTERN.match(slug):
            return _json_response(400, {"error": "slug must be lowercase alphanumeric + hyphen."})

        if template_id:
            tpl = table.get_item(Key=get_template_item(template_id)).get("Item")
            if not tpl:
                return _json_response(400, {"error": f"Template not found: {template_id}"})
            tenant = table.get_item(Key=get_tenant_item(tenant_slug)).get("Item")
            if tenant and _tier_rank(tenant.get("tier", "FREE")) < _tier_rank(tpl.get("tier_required", "FREE")):
                return _json_response(403, {"error": f"Template requires {tpl.get('tier_required')} tier."})

        site_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "pk": pk_tenant(tenant_slug),
            "sk": sk_site(site_id),
            "name": name,
            "slug": slug,
            "status": status,
            "created_at": now,
            "updated_at": now,
        }
        if template_id:
            item["template_id"] = template_id
        table.put_item(Item=item)
        return _json_response(201, {"site": _site_to_response(item)})

    if method == "PUT" and site_id:
        key = get_site_item(tenant_slug, site_id)
        item = table.get_item(Key=key).get("Item")
        if not item:
            return _json_response(404, {"error": "Site not found."})

        body = _parse_body(event) or {}
        if body.get("name") is not None:
            item["name"] = str(body["name"]).strip()
        if body.get("slug") is not None:
            s = str(body["slug"]).strip().lower()
            if not SITE_SLUG_PATTERN.match(s):
                return _json_response(400, {"error": "slug must be lowercase alphanumeric + hyphen."})
            item["slug"] = s
        if body.get("status") is not None:
            s = str(body["status"]).strip().lower()
            if s in ("draft", "published"):
                item["status"] = s
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        table.put_item(Item=item)
        return _json_response(200, {"site": _site_to_response(item)})

    if method == "DELETE" and site_id:
        key = get_site_item(tenant_slug, site_id)
        if not table.get_item(Key=key).get("Item"):
            return _json_response(404, {"error": "Site not found."})
        table.delete_item(Key=key)
        return _json_response(204, {}, empty_body=True)

    return _json_response(405, {"error": "Method not allowed."})


# --- Task 1.39: CRUD /api/admin/tenants/{slug}/users ---

MODULE_KEYS = ("sites", "domains", "analytics", "settings")


def _profile_to_response(item: dict) -> dict:
    sk = item.get("sk", "")
    sub = ""
    if sk.startswith("USER#") and sk.endswith("#PROFILE"):
        sub = sk.replace("USER#", "").replace("#PROFILE", "")
    return {
        "sub": sub or item.get("sub", ""),
        "email": item.get("email", ""),
        "name": item.get("name", ""),
        "role": item.get("role", "member"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def _get_user_email_name_from_cognito(sub: str, region: str) -> tuple[str, str]:
    """Fetch email and name from Cognito AdminGetUser. Username may be sub or email."""
    user_pool_id = os.environ.get("USER_POOL_ID", "")
    if not user_pool_id:
        return "", ""
    try:
        client = boto3.client("cognito-idp", region_name=region)
        resp = client.admin_get_user(
            UserPoolId=user_pool_id,
            Username=sub,
        )
        email, name = "", ""
        for attr in resp.get("UserAttributes", []):
            if attr.get("Name") == "email":
                email = attr.get("Value", "")
            elif attr.get("Name") in ("name", "preferred_username"):
                if not name:
                    name = attr.get("Value", "")
        if not name and resp.get("Username"):
            name = resp.get("Username", "")
        return email, name
    except Exception:
        return "", ""


def _get_cognito_sub_by_email(email: str, region: str) -> str | None:
    """Look up Cognito user sub by email. Returns sub or None if not found."""
    user_pool_id = os.environ.get("USER_POOL_ID", "")
    if not user_pool_id or not email:
        return None
    try:
        client = boto3.client("cognito-idp", region_name=region)
        # Try filter by email attribute first
        resp = client.list_users(
            UserPoolId=user_pool_id,
            Filter=f'email = "{email}"',
            Limit=1,
        )
        users = resp.get("Users", [])
        if not users:
            # Fallback: when "email as username" is enabled, try Username directly
            try:
                admin_resp = client.admin_get_user(
                    UserPoolId=user_pool_id,
                    Username=email,
                )
                for attr in admin_resp.get("UserAttributes", []):
                    if attr.get("Name") == "sub":
                        return attr.get("Value")
                return admin_resp.get("Username")
            except Exception:
                return None
        u = users[0]
        for attr in u.get("Attributes", []):
            if attr.get("Name") == "sub":
                return attr.get("Value")
        return u.get("Username")
    except Exception:
        return None


def admin_users_handler(event: dict, context: dict, tenant_slug: str, path_suffix: str) -> dict:
    """GET/POST /api/admin/tenants/{slug}/users, GET/PUT/DELETE /api/admin/tenants/{slug}/users/{sub}."""
    _, err = _require_superadmin(event)
    if err:
        return err

    table, err = _get_table()
    if err:
        return err

    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    if not resp.get("Item"):
        return _json_response(404, {"error": f"Tenant not found: {tenant_slug}"})

    method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "GET"
    )

    parts = path_suffix.strip("/").split("/")
    target_sub = unquote(parts[1]) if len(parts) > 1 else None
    is_permissions = len(parts) >= 3 and parts[2] == "permissions"

    if method == "GET" and not target_sub:
        # Fetch Cognito users (USER#)
        params = query_users_in_tenant(tenant_slug)
        resp = table.query(**params)
        users = []
        region = os.environ.get("AWS_REGION", "us-east-1")
        for it in resp.get("Items", []):
            if it.get("sk", "").endswith("#PROFILE"):
                u = _profile_to_response(it)
                sub = u.get("sub", "")
                if sub and (not u.get("email") or not u.get("name")):
                    e, n = _get_user_email_name_from_cognito(sub, region)
                    if e and not u.get("email"):
                        u["email"] = e
                    if n and not u.get("name"):
                        u["name"] = n
                users.append(u)

        # Fetch DB users (TUSER#)
        from dynamodb_helpers import query_tusers_in_tenant
        tuser_params = query_tusers_in_tenant(tenant_slug)
        tuser_resp = table.query(**tuser_params)
        for it in tuser_resp.get("Items", []):
            sk = it.get("sk", "")
            username = sk.replace("TUSER#", "") if sk.startswith("TUSER#") else ""
            users.append({
                "sub": username,  # Use username as sub for UI keying
                "email": "",
                "name": it.get("display_name") or username,
                "role": it.get("role", "member"),
                "created_at": it.get("created_at", ""),
                "updated_at": it.get("updated_at", ""),
                "type": "tuser"
            })

        return _json_response(200, {"users": users})

    if method == "GET" and target_sub and is_permissions:
        key = get_user_permissions_item(tenant_slug, target_sub)
        if not table.get_item(Key=get_user_profile_item(tenant_slug, target_sub)).get("Item"):
            if not table.get_item(Key=get_tuser_item(tenant_slug, target_sub)).get("Item"):
                return _json_response(404, {"error": "User not found in tenant."})
        item = table.get_item(Key=key).get("Item")
        perms = (item or {}).get("permissions", {})
        result = {k: perms.get(k, True) for k in MODULE_KEYS}
        return _json_response(200, {"permissions": result})

    if method == "PUT" and target_sub and is_permissions:
        if not table.get_item(Key=get_user_profile_item(tenant_slug, target_sub)).get("Item"):
            if not table.get_item(Key=get_tuser_item(tenant_slug, target_sub)).get("Item"):
                return _json_response(404, {"error": "User not found in tenant."})
        body = _parse_body(event) or {}
        perms = body.get("permissions", {})
        if not isinstance(perms, dict):
            return _json_response(400, {"error": "permissions must be an object."})
        existing = table.get_item(Key=get_user_permissions_item(tenant_slug, target_sub))
        current = (existing.get("Item") or {}).get("permissions", {})
        merged = {k: current.get(k, True) for k in MODULE_KEYS}
        for k in MODULE_KEYS:
            if k in perms:
                merged[k] = bool(perms[k])
        now = datetime.now(timezone.utc).isoformat()
        table.put_item(
            Item={
                "pk": pk_tenant(tenant_slug),
                "sk": sk_user_permissions(target_sub),
                "permissions": merged,
                "updated_at": now,
            }
        )
        return _json_response(200, {"permissions": merged})

    if method == "POST" and not target_sub:
        body = _parse_body(event) or {}
        user_type = (body.get("type") or "cognito").lower()

        if user_type == "tuser":
            # Task 2.70: Create non-Cognito (TUSER) user
            username_val = (body.get("username") or "").strip()
            password = body.get("password") or ""
            display_name = (body.get("display_name") or "").strip()
            role_val = (body.get("role") or "member").lower()

            if not username_val:
                return _json_response(400, {"error": "username is required for DB user."})
            if not password or len(password) < 8:
                return _json_response(400, {"error": "password is required and must be at least 8 characters."})
            if not USERNAME_PATTERN.match(username_val):
                return _json_response(400, {"error": "username must be alphanumeric, dots, underscores, hyphens."})
            if role_val not in ("manager", "member"):
                role_key = get_role_item(tenant_slug, role_val)
                if not table.get_item(Key=role_key).get("Item"):
                    return _json_response(400, {"error": "role must be manager, member, or an existing custom role."})

            key = get_tuser_item(tenant_slug, username_val)
            if table.get_item(Key=key).get("Item"):
                return _json_response(409, {"error": f"User {username_val} already exists in this tenant."})

            password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            now = datetime.now(timezone.utc).isoformat()
            item = {
                "pk": pk_tenant(tenant_slug),
                "sk": sk_tuser(username_val),
                "username": username_val,
                "password_hash": password_hash,
                "display_name": display_name,
                "role": role_val,
                "created_at": now,
                "updated_at": now,
                "gsi3pk": gsi3pk_entity_user(),
                "gsi3sk": gsi3sk_tuser(tenant_slug, username_val),
            }
            table.put_item(Item=item)
            return _json_response(201, {
                "user": {
                    "sub": username_val,
                    "email": "",
                    "name": display_name or username_val,
                    "role": role_val,
                    "created_at": now,
                    "updated_at": now,
                    "type": "tuser",
                },
            })

        # Cognito user
        sub = (body.get("sub") or "").strip()
        role = (body.get("role") or "member").lower()
        email = (body.get("email") or "").strip()
        name = (body.get("name") or "").strip()

        region = os.environ.get("AWS_REGION", "us-east-1")
        if not sub and email:
            sub = _get_cognito_sub_by_email(email, region) or ""
            if not sub:
                return _json_response(404, {"error": f"No Cognito user found with email: {email}"})
        if not sub:
            return _json_response(400, {"error": "sub or email is required."})
        if role not in ("admin", "manager", "editor", "member"):
            return _json_response(400, {"error": "role must be admin, manager, editor, or member."})

        if table.get_item(Key=get_user_profile_item(tenant_slug, sub)).get("Item"):
            return _json_response(409, {"error": "User already in tenant."})

        if not email or not name:
            e, n = _get_user_email_name_from_cognito(sub, region)
            email = email or e
            name = name or n

        now = datetime.now(timezone.utc).isoformat()
        item = {
            "pk": pk_tenant(tenant_slug),
            "sk": sk_user_profile(sub),
            "gsi1pk": gsi1pk_user(sub),
            "gsi1sk": gsi1sk_tenant_profile(tenant_slug),
            "gsi3pk": gsi3pk_entity_user(),
            "gsi3sk": gsi3sk_user(tenant_slug, sub),
            "sub": sub,
            "email": email,
            "name": name or sub[:8],
            "role": role,
            "created_at": now,
            "updated_at": now,
        }
        table.put_item(Item=item)
        return _json_response(201, {"user": _profile_to_response(item)})

    if method == "PUT" and target_sub and not is_permissions:
        key = get_user_profile_item(tenant_slug, target_sub)
        item = table.get_item(Key=key).get("Item")
        is_tuser = False
        if not item:
            key = get_tuser_item(tenant_slug, target_sub)
            item = table.get_item(Key=key).get("Item")
            is_tuser = True

        if not item:
            return _json_response(404, {"error": "User not found in tenant."})

        body = _parse_body(event) or {}
        if "role" in body:
            r = str(body["role"]).lower()
            if r in ("admin", "manager", "editor", "member"):
                item["role"] = r
        if not is_tuser:
            if "email" in body:
                item["email"] = str(body["email"]).strip()
            if "name" in body:
                item["name"] = str(body["name"]).strip()
        else:
            if "name" in body:
                item["display_name"] = str(body["name"]).strip()

        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        table.put_item(Item=item)
        if is_tuser:
            return _json_response(200, {"user": {
                "sub": target_sub,
                "email": "",
                "name": item.get("display_name") or target_sub,
                "role": item.get("role", "member"),
                "created_at": item.get("created_at", ""),
                "updated_at": item.get("updated_at", ""),
                "type": "tuser"
            }})
        return _json_response(200, {"user": _profile_to_response(item)})

    if method == "DELETE" and target_sub and not is_permissions:
        profile_key = get_user_profile_item(tenant_slug, target_sub)
        if not table.get_item(Key=profile_key).get("Item"):
            tuser_key = get_tuser_item(tenant_slug, target_sub)
            if table.get_item(Key=tuser_key).get("Item"):
                table.delete_item(Key=tuser_key)
                return _json_response(204, {}, empty_body=True)
            return _json_response(404, {"error": "User not found in tenant."})
        table.delete_item(Key=profile_key)
        perm_key = get_user_permissions_item(tenant_slug, target_sub)
        table.delete_item(Key=perm_key)
        return _json_response(204, {}, empty_body=True)

    return _json_response(405, {"error": "Method not allowed."})


# --- Task 2.70: GET /api/admin/tenants/{slug}/roles (superadmin list roles) ---

ADMIN_ROLE_MODULE_KEYS = ("sites", "domains", "analytics", "settings", "users")


def admin_roles_handler(event: dict, context: dict, tenant_slug: str) -> dict:
    """GET /api/admin/tenants/{slug}/roles — list custom roles (superadmin)."""
    _, err = _require_superadmin(event)
    if err:
        return err

    table, err = _get_table()
    if err:
        return err

    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    if not resp.get("Item"):
        return _json_response(404, {"error": f"Tenant not found: {tenant_slug}"})

    params = query_roles_in_tenant(tenant_slug)
    resp = table.query(**params)
    roles = []
    for it in resp.get("Items", []):
        sk = it.get("sk", "")
        name = sk.replace("ROLE#", "") if sk.startswith("ROLE#") else ""
        perms = it.get("permissions", {})
        roles.append({
            "name": name or it.get("name", ""),
            "permissions": {k: bool(perms.get(k, False)) for k in ADMIN_ROLE_MODULE_KEYS},
            "created_at": it.get("created_at", ""),
            "updated_at": it.get("updated_at", ""),
        })
    return _json_response(200, {"roles": roles})


# --- Task 1.40: PUT /api/admin/tenants/{slug}/settings ---

def put_tenant_settings_handler(event: dict, context: dict, tenant_slug: str) -> dict:
    """
    PUT /api/admin/tenants/{slug}/settings — update tenant settings (superadmin).
    Body: { tier?, name?, module_overrides?, owner_sub? }
    """
    _, err = _require_superadmin(event)
    if err:
        return err

    table, err = _get_table()
    if err:
        return err

    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    item = resp.get("Item")
    if not item:
        return _json_response(404, {"error": f"Tenant not found: {tenant_slug}"})

    body = _parse_body(event) or {}
    updates = []
    expr_vals = {}
    expr_names = {}

    if "tier" in body:
        tier = (body.get("tier") or "FREE").upper()
        if tier not in ("FREE", "PRO", "BUSINESS"):
            return _json_response(400, {"error": "tier must be FREE, PRO, or BUSINESS"})
        updates.append("tier = :tier")
        expr_vals[":tier"] = tier

    if "name" in body:
        name = (body.get("name") or "").strip()
        updates.append("#n = :name")
        expr_names["#n"] = "name"
        expr_vals[":name"] = name if name else tenant_slug

    if "module_overrides" in body:
        mo = body.get("module_overrides")
        if not isinstance(mo, dict):
            return _json_response(400, {"error": "module_overrides must be a map"})
        valid_keys = {"custom_domains", "advanced_analytics"}
        clean_mo = {k: bool(v) for k, v in mo.items() if k in valid_keys}
        updates.append("module_overrides = :mo")
        expr_vals[":mo"] = clean_mo

    if "owner_sub" in body:
        owner = (body.get("owner_sub") or "").strip() if body.get("owner_sub") else ""
        if owner:
            updates.append("owner_sub = :owner")
            expr_vals[":owner"] = owner

    if not updates:
        return _json_response(400, {"error": "Provide at least one of: tier, name, module_overrides, owner_sub"})

    now = datetime.now(timezone.utc).isoformat()
    updates.append("updated_at = :u")
    expr_vals[":u"] = now

    kwargs = {
        "Key": get_tenant_item(tenant_slug),
        "UpdateExpression": "SET " + ", ".join(updates),
        "ExpressionAttributeValues": expr_vals,
    }
    if expr_names:
        kwargs["ExpressionAttributeNames"] = expr_names

    table.update_item(**kwargs)

    resp = table.get_item(Key=get_tenant_item(tenant_slug))
    updated = resp.get("Item", {})
    owner_sub = updated.get("owner_sub")
    region = os.environ.get("AWS_REGION", "us-east-1")
    owner_email = _get_email_from_cognito_sub(owner_sub or "", region) if owner_sub else ""
    return _json_response(
        200,
        {
            "slug": tenant_slug,
            "name": updated.get("name", tenant_slug),
            "tier": updated.get("tier", "FREE"),
            "owner_sub": owner_sub,
            "owner_email": owner_email,
            "module_overrides": updated.get("module_overrides") or {},
            "updated_at": updated.get("updated_at"),
        },
    )
