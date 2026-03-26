"""
EventBridge handler: ACM certificate issued → add alias to CloudFront, update domain (Task 1.99, 1.100b, 1.147).

Triggered when an ACM certificate status changes to ISSUED (ACM Certificate Available event).
Looks up domain by cert ARN, adds alias to sites distribution, updates domain status to ACTIVE.
Zero polling — event-driven.
"""

import json
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

CLOUDFRONT_DISTRIBUTION_ID = os.environ.get("CLOUDFRONT_SITES_DISTRIBUTION_ID", "")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "9host-main")


def _add_cloudfront_alias(domain: str) -> bool:
    """Add domain as alias to CloudFront sites distribution."""
    if not CLOUDFRONT_DISTRIBUTION_ID:
        return False

    cf = boto3.client("cloudfront")
    try:
        config_resp = cf.get_distribution_config(Id=CLOUDFRONT_DISTRIBUTION_ID)
        config = config_resp["DistributionConfig"]
        etag = config_resp["ETag"]

        aliases = config.get("Aliases", {})
        items_list = list(aliases.get("Items") or [])
        if domain in items_list:
            return True  # already present

        items_list.append(domain)
        aliases["Items"] = items_list
        aliases["Quantity"] = len(items_list)
        config["Aliases"] = aliases

        cf.update_distribution(Id=CLOUDFRONT_DISTRIBUTION_ID, DistributionConfig=config, IfMatch=etag)
        return True
    except ClientError as e:
        print(f"[9host] CloudFront add alias failed for {domain}: {e}")
        raise


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

        # Add alias to CloudFront distribution (Task 1.99, 1.147)
        _add_cloudfront_alias(domain_name)

        # Update domain status to ACTIVE
        now = datetime.now(timezone.utc).isoformat()
        table.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression="SET #status = :status, updated_at = :now",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "ACTIVE", ":now": now},
        )

        return {"statusCode": 200, "body": json.dumps({"domain": domain_name, "status": "ACTIVE"})}

    except Exception as e:
        print(f"ACM handler error: {e}")
        raise
