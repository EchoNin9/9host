"""
EventBridge handler: ACM certificate issued → create per-domain CloudFront distribution,
update domain status to ACTIVE (Task 1.99, 1.100b, 1.147, custom-domain-distro).

Triggered when an ACM certificate status changes to ISSUED (ACM Certificate Available event).
Looks up domain by cert ARN, creates a dedicated CloudFront distribution for the domain,
stores distribution info in DynamoDB, updates domain status to ACTIVE.
Zero polling — event-driven.
"""

import json
import os
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "9host-main")
SITES_BUCKET_DOMAIN = os.environ.get("SITES_BUCKET_DOMAIN", "")
MEDIA_BUCKET_DOMAIN = os.environ.get("MEDIA_BUCKET_DOMAIN", "")
OAC_ID = os.environ.get("CLOUDFRONT_OAC_ID", "")
CF_FUNCTION_ARN = os.environ.get("CLOUDFRONT_CUSTOM_DOMAIN_FUNCTION_ARN", "")
CF_MEDIA_FUNCTION_ARN = os.environ.get("CLOUDFRONT_MEDIA_FUNCTION_ARN", "")


def _create_distribution(domain: str, cert_arn: str, tenant: str, site_id: str) -> dict:
    """Create a CloudFront distribution for a custom domain.

    Returns {'distribution_id': str, 'domain_name': str}.
    """
    www_domain = f"www.{domain}" if not domain.startswith("www.") else None
    aliases = [domain]
    if www_domain:
        aliases.append(www_domain)

    origin_path = f"/{tenant}/{site_id}/published/current"

    # Origins: sites (default) + media (for /media/* images)
    origins = [
        {
            "Id": "S3-9host-sites",
            "DomainName": SITES_BUCKET_DOMAIN,
            "OriginPath": origin_path,
            "S3OriginConfig": {"OriginAccessIdentity": ""},
            "OriginAccessControlId": OAC_ID,
        }
    ]
    if MEDIA_BUCKET_DOMAIN:
        origins.append({
            "Id": "S3-9host-media",
            "DomainName": MEDIA_BUCKET_DOMAIN,
            "OriginPath": "",
            "S3OriginConfig": {"OriginAccessIdentity": ""},
            "OriginAccessControlId": OAC_ID,
        })

    # /media/* behavior — route to media bucket with path rewrite
    cache_behaviors = []
    if MEDIA_BUCKET_DOMAIN and CF_MEDIA_FUNCTION_ARN:
        cache_behaviors.append({
            "PathPattern": "/media/*",
            "TargetOriginId": "S3-9host-media",
            "ViewerProtocolPolicy": "redirect-to-https",
            "AllowedMethods": {
                "Quantity": 3,
                "Items": ["GET", "HEAD", "OPTIONS"],
                "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
            },
            "Compress": True,
            "ForwardedValues": {
                "QueryString": False,
                "Cookies": {"Forward": "none"},
            },
            "MinTTL": 0,
            "DefaultTTL": 86400,
            "MaxTTL": 31536000,
            "FunctionAssociations": {
                "Quantity": 1,
                "Items": [
                    {
                        "EventType": "viewer-request",
                        "FunctionARN": CF_MEDIA_FUNCTION_ARN,
                    }
                ],
            },
        })

    config = {
        "CallerReference": f"9host-{domain}-{int(time.time())}",
        "Comment": f"9host custom domain: {domain}",
        "Enabled": True,
        "IsIPV6Enabled": True,
        "PriceClass": "PriceClass_100",
        "HttpVersion": "http2and3",
        "Aliases": {"Quantity": len(aliases), "Items": aliases},
        "Origins": {
            "Quantity": len(origins),
            "Items": origins,
        },
        "CacheBehaviors": {
            "Quantity": len(cache_behaviors),
            "Items": cache_behaviors,
        } if cache_behaviors else {"Quantity": 0},
        "DefaultCacheBehavior": {
            "TargetOriginId": "S3-9host-sites",
            "ViewerProtocolPolicy": "redirect-to-https",
            "AllowedMethods": {
                "Quantity": 3,
                "Items": ["GET", "HEAD", "OPTIONS"],
                "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
            },
            "Compress": True,
            "ForwardedValues": {
                "QueryString": False,
                "Cookies": {"Forward": "none"},
            },
            "MinTTL": 0,
            "DefaultTTL": 60,
            "MaxTTL": 300,
            "FunctionAssociations": {
                "Quantity": 1,
                "Items": [
                    {
                        "EventType": "viewer-request",
                        "FunctionARN": CF_FUNCTION_ARN,
                    }
                ],
            },
        },
        "ViewerCertificate": {
            "ACMCertificateArn": cert_arn,
            "SSLSupportMethod": "sni-only",
            "MinimumProtocolVersion": "TLSv1.2_2021",
        },
        "Restrictions": {
            "GeoRestriction": {"RestrictionType": "none", "Quantity": 0}
        },
    }

    cf = boto3.client("cloudfront")
    resp = cf.create_distribution(DistributionConfig=config)
    dist = resp.get("Distribution", {})
    return {
        "distribution_id": dist.get("Id", ""),
        "domain_name": dist.get("DomainName", ""),
    }


def lambda_handler(event: dict, context: dict) -> dict:
    """Handle EventBridge ACM Certificate Available event."""
    try:
        if event.get("detail-type") != "ACM Certificate Available":
            return {"statusCode": 200, "body": "Ignored event type"}

        resources = event.get("resources") or []
        cert_arn = resources[0] if resources else ""

        if not cert_arn or "arn:aws:acm:" not in cert_arn:
            return {"statusCode": 200, "body": "No cert ARN"}

        # Get domain name from ACM cert
        acm = boto3.client("acm", region_name="us-east-1")
        try:
            cert = acm.describe_certificate(CertificateArn=cert_arn)
        except ClientError:
            return {"statusCode": 200, "body": "Cert not found"}

        domain_name = cert.get("Certificate", {}).get("DomainName", "").strip().lower()
        if not domain_name:
            return {"statusCode": 200, "body": "No domain in cert"}

        # Find domain record with this cert ARN
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(DYNAMODB_TABLE)
        scan_resp = table.scan(
            FilterExpression="attribute_exists(acm_certificate_arn) AND acm_certificate_arn = :arn",
            ExpressionAttributeValues={":arn": cert_arn},
        )
        items = scan_resp.get("Items", [])
        while scan_resp.get("LastEvaluatedKey"):
            scan_resp = table.scan(
                FilterExpression="attribute_exists(acm_certificate_arn) AND acm_certificate_arn = :arn",
                ExpressionAttributeValues={":arn": cert_arn},
                ExclusiveStartKey=scan_resp["LastEvaluatedKey"],
            )
            items.extend(scan_resp.get("Items", []))

        if not items:
            return {"statusCode": 200, "body": "No domain record for cert"}

        domain_item = items[0]
        pk = domain_item.get("pk", "")
        sk = domain_item.get("sk", "")
        tenant_slug = pk.replace("TENANT#", "") if pk.startswith("TENANT#") else ""
        site_id = domain_item.get("site_id", "")

        # Skip if distribution already exists
        if domain_item.get("cloudfront_distribution_id"):
            return {"statusCode": 200, "body": "Distribution already exists"}

        if not tenant_slug or not site_id:
            return {"statusCode": 200, "body": "Missing tenant or site_id"}

        if not SITES_BUCKET_DOMAIN or not OAC_ID or not CF_FUNCTION_ARN:
            print(f"[9host] Missing env vars for distribution creation: "
                  f"SITES_BUCKET_DOMAIN={SITES_BUCKET_DOMAIN}, OAC_ID={OAC_ID}, "
                  f"CF_FUNCTION_ARN={CF_FUNCTION_ARN}")
            return {"statusCode": 500, "body": "Missing configuration"}

        # Create per-domain CloudFront distribution
        dist_info = _create_distribution(
            domain=domain_name,
            cert_arn=cert_arn,
            tenant=tenant_slug,
            site_id=site_id,
        )

        # Update domain record: ACTIVE + distribution info
        now = datetime.now(timezone.utc).isoformat()
        table.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression=(
                "SET #status = :status, updated_at = :now, "
                "cloudfront_distribution_id = :dist_id, "
                "cloudfront_domain_name = :dist_dn"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "ACTIVE",
                ":now": now,
                ":dist_id": dist_info["distribution_id"],
                ":dist_dn": dist_info["domain_name"],
            },
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "domain": domain_name,
                "status": "ACTIVE",
                "distribution_id": dist_info["distribution_id"],
                "distribution_domain": dist_info["domain_name"],
            }),
        }

    except Exception as e:
        print(f"ACM handler error: {e}")
        raise
