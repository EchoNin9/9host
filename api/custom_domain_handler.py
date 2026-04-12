"""
Custom domain SSL + CloudFront handler (Task 1.146, 1.147, custom-domain-distro).

Centralized ACM certificate + per-domain CloudFront distribution operations.
Each custom domain gets its own distribution with:
  - Origin: 9host-sites S3, path /{tenant}/{site_id}/published/current
  - CF function for path resolution + www→apex redirect
  - Per-domain ACM cert covering domain.com + www.domain.com
  - Aliases: domain.com, www.domain.com
"""

import json
import os
import time

import boto3
from botocore.exceptions import ClientError

# Env vars set by OpenTofu
SITES_BUCKET_DOMAIN = os.environ.get("SITES_BUCKET_DOMAIN", "")
MEDIA_BUCKET_DOMAIN = os.environ.get("MEDIA_BUCKET_DOMAIN", "")
OAC_ID = os.environ.get("CLOUDFRONT_OAC_ID", "")
CF_FUNCTION_ARN = os.environ.get("CLOUDFRONT_CUSTOM_DOMAIN_FUNCTION_ARN", "")
CF_MEDIA_FUNCTION_ARN = os.environ.get("CLOUDFRONT_MEDIA_FUNCTION_ARN", "")

# Legacy — kept for backward compat during migration
CLOUDFRONT_SITES_DISTRIBUTION_ID = os.environ.get("CLOUDFRONT_SITES_DISTRIBUTION_ID", "")


def request_acm_certificate(domain: str) -> tuple[str, list[dict]]:
    """Request an ACM certificate for domain + www.domain (SAN).

    Requests DNS-validated cert in us-east-1 (required for CloudFront).
    Retries up to 5 times (2s apart) to fetch validation CNAME records.

    Returns:
        (cert_arn, validation_records) where validation_records is a list of
        {"type": str, "name": str, "value": str} dicts.

    Raises:
        RuntimeError on failure.
    """
    acm = boto3.client("acm", region_name="us-east-1")

    www_domain = f"www.{domain}" if not domain.startswith("www.") else None

    try:
        kwargs: dict = {"DomainName": domain, "ValidationMethod": "DNS"}
        if www_domain:
            kwargs["SubjectAlternativeNames"] = [domain, www_domain]
        resp = acm.request_certificate(**kwargs)
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
                    entry = {
                        "type": rec.get("Type", ""),
                        "name": rec.get("Name", ""),
                        "value": rec.get("Value", ""),
                    }
                    # Deduplicate (domain + www often share the same validation record)
                    if entry not in validation_records:
                        validation_records.append(entry)
            if validation_records:
                break
        except ClientError:
            pass
        time.sleep(2)

    return cert_arn, validation_records


def create_custom_domain_distribution(
    domain: str,
    cert_arn: str,
    tenant: str,
    site_id: str,
) -> dict:
    """Create a CloudFront distribution for a custom domain.

    Returns dict with 'distribution_id' and 'domain_name' (e.g. d123.cloudfront.net).
    Raises RuntimeError on failure.
    """
    sites_bucket = SITES_BUCKET_DOMAIN
    media_bucket = MEDIA_BUCKET_DOMAIN
    oac_id = OAC_ID
    cf_func_arn = CF_FUNCTION_ARN
    cf_media_func_arn = CF_MEDIA_FUNCTION_ARN

    if not sites_bucket or not oac_id or not cf_func_arn:
        raise RuntimeError(
            "Missing env: SITES_BUCKET_DOMAIN, CLOUDFRONT_OAC_ID, "
            "or CLOUDFRONT_CUSTOM_DOMAIN_FUNCTION_ARN"
        )

    www_domain = f"www.{domain}" if not domain.startswith("www.") else None
    aliases = [domain]
    if www_domain:
        aliases.append(www_domain)

    origin_path = f"/{tenant}/{site_id}/published/current"

    # Origins: sites (default) + media (for /media/* images)
    origins = [
        {
            "Id": "S3-9host-sites",
            "DomainName": sites_bucket,
            "OriginPath": origin_path,
            "S3OriginConfig": {"OriginAccessIdentity": ""},
            "OriginAccessControlId": oac_id,
        }
    ]
    if media_bucket:
        origins.append({
            "Id": "S3-9host-media",
            "DomainName": media_bucket,
            "OriginPath": "",
            "S3OriginConfig": {"OriginAccessIdentity": ""},
            "OriginAccessControlId": oac_id,
        })

    # /media/* behavior — route to media bucket with CF function for path rewrite
    cache_behaviors = []
    if media_bucket and cf_media_func_arn:
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
                        "FunctionARN": cf_media_func_arn,
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
                        "FunctionARN": cf_func_arn,
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
    try:
        resp = cf.create_distribution(DistributionConfig=config)
        dist = resp.get("Distribution", {})
        return {
            "distribution_id": dist.get("Id", ""),
            "domain_name": dist.get("DomainName", ""),
        }
    except ClientError as e:
        raise RuntimeError(f"Failed to create distribution for {domain}: {e}") from e


def disable_custom_domain_distribution(distribution_id: str) -> bool:
    """Disable a CloudFront distribution (first step before deletion).

    Returns True on success, False on failure.
    """
    if not distribution_id:
        return True

    cf = boto3.client("cloudfront")
    try:
        config_resp = cf.get_distribution_config(Id=distribution_id)
        config = config_resp["DistributionConfig"]
        etag = config_resp["ETag"]

        if not config.get("Enabled", True):
            return True  # already disabled

        config["Enabled"] = False
        # Remove aliases so the domain can be reused immediately
        config["Aliases"] = {"Quantity": 0, "Items": []}
        # Switch to default cert since aliases are removed
        config["ViewerCertificate"] = {
            "CloudFrontDefaultCertificate": True,
            "MinimumProtocolVersion": "TLSv1.2_2021",
        }

        cf.update_distribution(Id=distribution_id, DistributionConfig=config, IfMatch=etag)
        return True
    except ClientError as e:
        print(f"[9host] CloudFront disable failed for {distribution_id}: {e}")
        return False


def delete_custom_domain_distribution(distribution_id: str) -> bool:
    """Delete a disabled CloudFront distribution.

    The distribution must be disabled and fully deployed first.
    Returns True on success, False if not yet ready or on failure.
    """
    if not distribution_id:
        return True

    cf = boto3.client("cloudfront")
    try:
        resp = cf.get_distribution(Id=distribution_id)
        status = resp.get("Distribution", {}).get("Status", "")
        etag = resp.get("ETag", "")

        if status != "Deployed":
            return False  # not ready for deletion yet

        config = resp.get("Distribution", {}).get("DistributionConfig", {})
        if config.get("Enabled", True):
            return False  # still enabled

        cf.delete_distribution(Id=distribution_id, IfMatch=etag)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code == "NoSuchDistribution":
            return True  # already gone
        print(f"[9host] CloudFront delete failed for {distribution_id}: {e}")
        return False


def add_cloudfront_alias(domain: str, distribution_id: str | None = None) -> bool:
    """Add a custom domain as an alias to the CloudFront sites distribution.

    Legacy function — kept for backward compat during migration.
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

    Legacy function — kept for backward compat during migration.
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
