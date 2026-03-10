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


def sk_site(site_id: str) -> str:
    return f"SITE#{site_id}"


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


def get_tenant_item(tenant_slug: str) -> dict[str, Any]:
    """GetItem params for tenant metadata."""
    return {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_tenant(),
    }


def get_user_profile_item(tenant_slug: str, sub: str) -> dict[str, Any]:
    """GetItem params for user profile in tenant."""
    return {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_user_profile(sub),
    }


def get_site_item(tenant_slug: str, site_id: str) -> dict[str, Any]:
    """GetItem params for site in tenant."""
    return {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_site(site_id),
    }


def query_users_in_tenant(tenant_slug: str) -> dict[str, Any]:
    """Query params: list users in tenant."""
    return {
        "KeyConditionExpression": "pk = :pk AND begins_with(sk, :sk_prefix)",
        "ExpressionAttributeValues": {
            ":pk": pk_tenant(tenant_slug),
            ":sk_prefix": "USER#",
        },
    }


def query_sites_in_tenant(tenant_slug: str) -> dict[str, Any]:
    """Query params: list sites in tenant."""
    return {
        "KeyConditionExpression": "pk = :pk AND begins_with(sk, :sk_prefix)",
        "ExpressionAttributeValues": {
            ":pk": pk_tenant(tenant_slug),
            ":sk_prefix": "SITE#",
        },
    }


def get_domain_item(tenant_slug: str, domain: str) -> dict[str, Any]:
    """GetItem params for domain in tenant."""
    return {
        "pk": pk_tenant(tenant_slug),
        "sk": sk_domain(domain),
    }


def query_domains_in_tenant(tenant_slug: str) -> dict[str, Any]:
    """Query params: list domains in tenant."""
    return {
        "KeyConditionExpression": "pk = :pk AND begins_with(sk, :sk_prefix)",
        "ExpressionAttributeValues": {
            ":pk": pk_tenant(tenant_slug),
            ":sk_prefix": "DOMAIN#",
        },
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
