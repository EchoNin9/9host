"""
CloudNS site CNAME sync (Task 1.103).

Add/delete {site-slug}.{zone} CNAME records on site create/update/delete.
Uses CloudNS HTTP API. Best-effort: logs errors, does not fail site operations.
"""

import json
import logging
import os
import urllib.request
import urllib.parse

import boto3

logger = logging.getLogger(__name__)

CLOUDNS_ADD_RECORD = "https://api.cloudns.net/dns/add-record.json"
CLOUDNS_DELETE_RECORD = "https://api.cloudns.net/dns/delete-record.json"
CLOUDNS_LIST_RECORDS = "https://api.cloudns.net/dns/records.json"


def _get_cloudns_creds() -> dict | None:
    """Fetch CloudNS credentials from Secrets Manager. Returns None if not configured."""
    secret_arn = os.environ.get("CLOUDNS_SECRET_ARN", "").strip()
    if not secret_arn:
        return None
    try:
        client = boto3.client("secretsmanager")
        resp = client.get_secret_value(SecretId=secret_arn)
        data = json.loads(resp.get("SecretString", "{}"))
        auth_id = data.get("auth_id")
        password = data.get("password")
        if auth_id is None or not password:
            return None
        return {"auth_id": auth_id, "password": password}
    except Exception as e:
        logger.warning("CloudNS: failed to get credentials: %s", e)
        return None


def _cloudns_request(url: str, data: dict) -> dict | None:
    """POST to CloudNS API. Returns parsed JSON or None on error."""
    try:
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("CloudNS API request failed: %s", e)
        return None


def add_site_cname(site_slug: str) -> bool:
    """
    Add CNAME record {site_slug}.{zone} -> CloudFront sites domain.
    Returns True on success, False otherwise. No-op if CloudNS not configured.
    """
    creds = _get_cloudns_creds()
    zone = (os.environ.get("CLOUDNS_ZONE") or "").strip()
    target = (os.environ.get("CLOUDNS_CF_TARGET") or os.environ.get("CLOUDFRONT_SITES_DOMAIN") or "").strip()
    if not creds or not zone or not target or not site_slug:
        return False
    data = {
        "auth-id": creds["auth_id"],
        "auth-password": creds["password"],
        "domain-name": zone,
        "record-type": "CNAME",
        "host": site_slug,
        "record": target.rstrip("."),
        "ttl": 300,
    }
    resp = _cloudns_request(CLOUDNS_ADD_RECORD, data)
    if not resp:
        return False
    status = resp.get("status", "")
    if status == "Success":
        logger.info("CloudNS: added CNAME %s.%s -> %s", site_slug, zone, target)
        return True
    logger.warning("CloudNS add-record failed: %s", resp.get("statusDescription", resp))
    return False


def delete_site_cname(site_slug: str) -> bool:
    """
    Delete CNAME record for {site_slug}.{zone}.
    Returns True on success, False otherwise. No-op if CloudNS not configured.
    """
    creds = _get_cloudns_creds()
    zone = (os.environ.get("CLOUDNS_ZONE") or "").strip()
    if not creds or not zone or not site_slug:
        return False
    # List records to find record-id for this host
    list_data = {
        "auth-id": creds["auth_id"],
        "auth-password": creds["password"],
        "domain-name": zone,
        "host": site_slug,
        "type": "CNAME",
        "rows-per-page": 10,
    }
    resp = _cloudns_request(CLOUDNS_LIST_RECORDS, list_data)
    if not resp or isinstance(resp, dict) and resp.get("status") == "Failed":
        return False
    records = resp if isinstance(resp, list) else []
    record_id = None
    for r in records:
        if isinstance(r, dict) and r.get("host") == site_slug and r.get("type", "").upper() == "CNAME":
            record_id = r.get("id")
            break
    if record_id is None:
        logger.info("CloudNS: no CNAME record found for %s.%s (may already be deleted)", site_slug, zone)
        return True
    del_data = {
        "auth-id": creds["auth_id"],
        "auth-password": creds["password"],
        "domain-name": zone,
        "record-id": record_id,
    }
    del_resp = _cloudns_request(CLOUDNS_DELETE_RECORD, del_data)
    if not del_resp:
        return False
    if del_resp.get("status") == "Success":
        logger.info("CloudNS: deleted CNAME %s.%s", site_slug, zone)
        return True
    logger.warning("CloudNS delete-record failed: %s", del_resp.get("statusDescription", del_resp))
    return False
