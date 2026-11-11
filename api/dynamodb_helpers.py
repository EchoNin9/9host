"""
DynamoDB helpers for 9host single-table schema.

Every query MUST use a Partition Key starting with TENANT#.
See docs/SCHEMA.md for entity layout and access patterns.
"""

from typing import Any

# Key builders — always prefix with TENANT#
def pk_tenant(slug: str) -> str:
    return f"TENANT#{slug}"


def sk_tenant() -> str:
    return "TENANT"


def sk_user_profile(sub: str) -> str:
    return f"USER#{sub}#PROFILE"


def sk_user_permissions(sub: str) -> str:
    return f"USER#{sub}#PERMISSIONS"


def sk_site(site_id: str) -> str:
    """Legacy site metadata SK. Collides with content prefix SITE#{id}#... (Bug #3)."""
    return f"SITE#{site_id}"


# Bug #3: site metadata lives at SITE_META#{id} (mirrored to legacy SITE#{id} during
# expand-contract). "SITE_META#" never prefixes content rows, so listing is O(sites).
SITE_META_PREFIX = "SITE_META#"


def sk_site_meta(site_id: str) -> str:
    return f"{SITE_META_PREFIX}{site_id}"


def sk_domain(domain: str) -> str:
    return f"DOMAIN#{domain.lower()}"


# GSI keys for byUser (user -> tenants)
def gsi1pk_user(sub: str) -> str:
    return f"USER#{sub}"


def gsi1sk_tenant_profile(slug: str) -> str:
    return f"TENANT#{slug}#PROFILE"


# GSI keys for byDomain (domain -> tenant)
def gsi2pk_domain(domain: str) -> str:
    return f"DOMAIN#{domain.lower()}"


def gsi2sk_tenant(slug: str) -> str:
    return f"TENANT#{slug}"


# GSI3 keys for byEntity (all users across tenants — superadmin)
ENTITY_USER = "ENTITY#USER"


def gsi3pk_entity_user() -> str:
    return ENTITY_USER


def gsi3sk_user(tenant_slug: str, sub: str) -> str:
    """For Cognito USER# items."""
    return f"TENANT#{tenant_slug}#USER#{sub}"


def gsi3sk_tuser(tenant_slug: str, username: str) -> str:
    """For non-Cognito TUSER# items."""
    return f"TENANT#{tenant_slug}#TUSER#{username}"


# GSI4 keys for bySiteSlug (Task 1.76)
def gsi4pk_slug(site_slug: str) -> str:
    """Partition key for bySiteSlug GSI."""
    return f"SLUG#{site_slug.lower()}"


def gsi4sk_site(site_id: str) -> str:
    """Sort key for bySiteSlug GSI."""
    return f"SITE#{site_id}"


def query_by_site_slug(site_slug: str) -> dict[str, Any]:
    """Query GSI bySiteSlug: check if site slug is taken globally."""
    return {
        "IndexName": "bySiteSlug",
        "KeyConditionExpression": "gsi4pk = :pk",
        "ExpressionAttributeValues": {
            ":pk": gsi4pk_slug(site_slug),
        },
    }


def slug_is_taken(table, slug: str, exclude_site_id: str | None = None) -> bool:
    """
    Check if slug is taken by a tenant or site (Task 1.77).
    Returns True if taken. Pass exclude_site_id when updating a site to allow keeping its own slug.
    """
    slug_lower = slug.strip().lower()
    if not slug_lower:
        return True
    # Tenant slugs are reserved (Task 1.76)
    tenant_key = get_tenant_item(slug_lower)
    if table.get_item(Key=tenant_key).get("Item"):
        return True
    # Check sites via bySiteSlug GSI
    params = query_by_site_slug(slug_lower)
    resp = table.query(**params)
    for item in resp.get("Items", []):
        sk = item.get("sk", "")
        site_id = sk.replace("SITE#", "") if sk.startswith("SITE#") else ""
        if exclude_site_id and site_id == exclude_site_id:
            continue
        return True
    return False


def sk_tuser(username: str) -> str:
    return f"TUSER#{username}"


def sk_role(name: str) -> str:
    return f"ROLE#{name}"


def get_tenant_item(tenant_slug: str) -> dict[str, Any]:
    """GetItem params for tenant metadata."""
    return {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_tenant(),
    }


def query_tenants_for_user(sub: str) -> dict[str, Any]:
    """Query GSI byUser: list tenants for Cognito user."""
    return {
        "IndexName": "byUser",
        "KeyConditionExpression": "gsi1pk = :pk AND begins_with(gsi1sk, :sk_prefix)",
        "ExpressionAttributeValues": {
            ":pk": gsi1pk_user(sub),
            ":sk_prefix": "TENANT#",
        },
    }


# Platform templates (Task 1.30) — PK=TENANT#_platform, SK=TEMPLATE#{slug}
PLATFORM_TENANT = "_platform"


def sk_template(slug: str) -> str:
    return f"TEMPLATE#{slug}"


def get_template_item(slug: str) -> dict[str, Any]:
    """GetItem params for platform template."""
    return {
        "pk": pk_tenant(PLATFORM_TENANT),
        "sk": sk_template(slug),
    }


def get_tenant_template_item(tenant_slug: str, template_slug: str) -> dict[str, Any]:
    """GetItem params for tenant-owned template (Task 1.123)."""
    return {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_template(template_slug),
    }


def query_tenant_templates(tenant_slug: str) -> dict[str, Any]:
    """Query params: list tenant's templates (forked)."""
    return {
        "KeyConditionExpression": "pk = :pk AND begins_with(sk, :sk_prefix)",
        "ExpressionAttributeValues": {
            ":pk": pk_tenant(tenant_slug),
            ":sk_prefix": "TEMPLATE#",
        },
    }


def query_templates() -> dict[str, Any]:
    """Query params: list all platform templates."""
    return {
        "KeyConditionExpression": "pk = :pk AND begins_with(sk, :sk_prefix)",
        "ExpressionAttributeValues": {
            ":pk": pk_tenant(PLATFORM_TENANT),
            ":sk_prefix": "TEMPLATE#",
        },
    }


def query_all_users_by_entity() -> dict[str, Any]:
    """Query GSI byEntity: list all users across tenants (superadmin)."""
    return {
        "IndexName": "byEntity",
        "KeyConditionExpression": "gsi3pk = :pk",
        "ExpressionAttributeValues": {
            ":pk": gsi3pk_entity_user(),
        },
    }
