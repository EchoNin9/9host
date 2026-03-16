"""
EventBridge handler: ACM certificate issued → add alias to CloudFront, update domain (Task 1.99, 1.100b).

Triggered when an ACM certificate status changes to ISSUED (ACM Certificate Available event).
Looks up domain by cert ARN, adds alias to sites distribution, updates domain status to ACTIVE.
Zero polling — event-driven.
"""

import json
import os

import boto3
from botocore.exceptions import ClientError

CLOUDFRONT_DISTRIBUTION_ID = os.environ.get("CLOUDFRONT_SITES_DISTRIBUTION_ID", "")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "9host-main")


def lambda_handler(event: dict, context: dict) -> dict:
    """Handle EventBridge ACM Certificate Available event."""
    try:
        # ACM Certificate Available: detail-type "ACM Certificate Available", cert ARN in resources[0]
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

        # Add alias to CloudFront distribution (Task 1.99)
        # CloudFront requires each alias to be in a cert. The sites distribution
        # uses wildcard cert for *.echo9.net. Custom domains need certs that cover
        # them. Per plan: one cert per domain. CloudFront supports multiple certs
        # per distribution; we add the alias and the domain's cert.
        if CLOUDFRONT_DISTRIBUTION_ID:
            cf = boto3.client("cloudfront")
            config_resp = cf.get_distribution_config(Id=CLOUDFRONT_DISTRIBUTION_ID)
            config = config_resp["DistributionConfig"]
            etag = config_resp["ETag"]

            aliases = config.get("Aliases", {})
            items_list = list(aliases.get("Items") or [])
            if domain_name not in items_list:
                items_list.append(domain_name)
                aliases["Items"] = items_list
                aliases["Quantity"] = len(items_list)
                config["Aliases"] = aliases

                if "ETag" in config:
                    del config["ETag"]

                try:
                    cf.update_distribution(
                        Id=CLOUDFRONT_DISTRIBUTION_ID,
                        DistributionConfig=config,
                        IfMatch=etag,
                    )
                except ClientError as e:
                    # Alias may require cert covering it; distribution has wildcard only.
                    # Task 1.100 will request domain cert; Terraform may need to add
                    # cert to distribution for multi-cert support.
                    print(f"CloudFront update failed (alias may need cert): {e}")
                    raise

        # Update domain status to ACTIVE
        from datetime import datetime, timezone

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
