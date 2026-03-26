"""
Custom domain SSL handler (Task 1.146, 1.147).

Centralized ACM certificate + CloudFront alias operations for custom domains.
Used by domains_handler (activate) and domain deletion (cleanup).
"""

import json
import os
import time

import boto3
from botocore.exceptions import ClientError

CLOUDFRONT_SITES_DISTRIBUTION_ID = os.environ.get("CLOUDFRONT_SITES_DISTRIBUTION_ID", "")


def request_acm_certificate(domain: str) -> tuple[str, list[dict]]:
    """Request an ACM certificate for a custom domain and return (arn, validation_records).

    Requests DNS-validated cert in us-east-1 (required for CloudFront).
    Retries up to 5 times (2s apart) to fetch validation CNAME records.

    Returns:
        (cert_arn, validation_records) where validation_records is a list of
        {"type": str, "name": str, "value": str} dicts.

    Raises:
        RuntimeError on failure.
    """
    acm = boto3.client("acm", region_name="us-east-1")

    try:
        resp = acm.request_certificate(DomainName=domain, ValidationMethod="DNS")
        cert_arn = resp.get("CertificateArn", "")
    except ClientError as e:
        raise RuntimeError(f"Failed to request certificate: {e}") from e

    if not cert_arn:
        raise RuntimeError("ACM did not return certificate ARN.")

    # Fetch validation records (ACM may take a few seconds to populate)
    validation_records: list[dict] = []
    for _ in range(5):
        try:
            desc = acm.describe_certificate(CertificateArn=cert_arn)
            opts = desc.get("Certificate", {}).get("DomainValidationOptions", [])
            for opt in opts:
                rec = opt.get("ResourceRecord")
                if rec:
                    validation_records.append({
                        "type": rec.get("Type", ""),
                        "name": rec.get("Name", ""),
                        "value": rec.get("Value", ""),
                    })
            if validation_records:
                break
        except ClientError:
            pass
        time.sleep(2)

    return cert_arn, validation_records


def add_cloudfront_alias(domain: str, distribution_id: str | None = None) -> bool:
    """Add a custom domain as an alias to the CloudFront sites distribution.

    Returns True if alias was added (or already present), False on failure.
    """
    dist_id = distribution_id or CLOUDFRONT_SITES_DISTRIBUTION_ID
    if not dist_id:
        return False

    cf = boto3.client("cloudfront")
    try:
        config_resp = cf.get_distribution_config(Id=dist_id)
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

        cf.update_distribution(Id=dist_id, DistributionConfig=config, IfMatch=etag)
        return True
    except ClientError as e:
        print(f"[9host] CloudFront add alias failed for {domain}: {e}")
        return False


def remove_cloudfront_alias(domain: str, distribution_id: str | None = None) -> bool:
    """Remove a custom domain alias from the CloudFront sites distribution.

    Returns True if removed (or not present), False on failure.
    """
    dist_id = distribution_id or CLOUDFRONT_SITES_DISTRIBUTION_ID
    if not dist_id:
        return True  # nothing to remove

    cf = boto3.client("cloudfront")
    try:
        config_resp = cf.get_distribution_config(Id=dist_id)
        config = config_resp["DistributionConfig"]
        etag = config_resp["ETag"]

        aliases = config.get("Aliases", {})
        items_list = list(aliases.get("Items") or [])
        if domain not in items_list:
            return True  # not present

        items_list.remove(domain)
        aliases["Items"] = items_list
        aliases["Quantity"] = len(items_list)
        config["Aliases"] = aliases

        cf.update_distribution(Id=dist_id, DistributionConfig=config, IfMatch=etag)
        return True
    except ClientError as e:
        print(f"[9host] CloudFront remove alias failed for {domain}: {e}")
        return False


def delete_acm_certificate(cert_arn: str) -> bool:
    """Delete an ACM certificate. Returns True on success, False on failure."""
    if not cert_arn:
        return True
    acm = boto3.client("acm", region_name="us-east-1")
    try:
        acm.delete_certificate(CertificateArn=cert_arn)
        return True
    except ClientError as e:
        # ResourceInUseException means cert is still attached — can't delete yet
        print(f"[9host] ACM delete failed for {cert_arn}: {e}")
        return False
