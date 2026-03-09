"""
Example Lambda handler using tenant middleware.

Shows how to use with_tenant and tenant_slug for DynamoDB queries.
"""

import json

from middleware import extract_tenant_slug, with_tenant


@with_tenant
def get_tenant_handler(event: dict, context: dict) -> dict:
    """
    Example: Get tenant metadata. Requires tenant_slug from subdomain or header.
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing tenant. Use subdomain (acme.echo9.net) or X-Tenant-Slug header."}),
        }

    # In real impl: use boto3 DynamoDB with get_tenant_item(tenant_slug)
    # from dynamodb_helpers import get_tenant_item
    # table.get_item(Key=get_tenant_item(tenant_slug))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "tenant_slug": tenant_slug,
            "message": "Tenant resolved. Use event.tenant_slug in DynamoDB queries.",
        }),
    }


def raw_handler(event: dict, context: dict) -> dict:
    """
    Example without decorator: manually extract tenant_slug.
    """
    tenant_slug = extract_tenant_slug(event)
    event["tenant_slug"] = tenant_slug
    # ... rest of handler
    return {"statusCode": 200, "body": json.dumps({"tenant_slug": tenant_slug})}
