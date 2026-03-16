"""
Default site resolution (Task 1.98).

GET /api/tenant/default-site — returns {site_id} for tenant's default published site.
Reads from S3 {tenant}/default.json written by publish flow.
"""

import json
import os

import boto3
from botocore.exceptions import ClientError as BotoClientError

from middleware import with_tenant

S3_SITES_BUCKET = "9host-sites"


def _json_response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


@with_tenant
def default_site_handler(event: dict, context: dict) -> dict:
    """
    GET /api/tenant/default-site — tenant's default site ID (Task 1.98).
    No auth required for public site resolution.
    """
    tenant_slug = event.get("tenant_slug")
    if not tenant_slug:
        return _json_response(400, {"error": "Missing tenant. Use subdomain or X-Tenant-Slug header."})

    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        return _json_response(500, {"error": "DYNAMODB_TABLE not configured"})

    region = os.environ.get("AWS_REGION", "us-east-1")
    s3_client = boto3.client("s3", region_name=region)

    try:
        obj = s3_client.get_object(Bucket=S3_SITES_BUCKET, Key=f"{tenant_slug}/default.json")
        data = json.loads(obj["Body"].read().decode())
        site_id = data.get("site_id")
        if not site_id:
            return _json_response(404, {"error": "No default site."})
        return _json_response(200, {"site_id": site_id})
    except BotoClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return _json_response(404, {"error": "No default site."})
        return _json_response(500, {"error": "Failed to resolve default site."})
