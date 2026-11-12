"""
Tenant slug extraction (used by ``request_context.build_request_context``) and input validators.

Sources (in order of precedence):
  1. X-Tenant-Slug header (for API clients)
  2. Host header subdomain (e.g. acme.echo9.net -> acme)
  3. Path parameter: /{tenant}/...

Superadmin X-Impersonate-Tenant is resolved in ``request_context``. All DynamoDB queries MUST
use TENANT#{tenant_slug}.
"""

import json
import re
from typing import Any

from reserved_slugs import RESERVED_SLUGS

# Slug: lowercase alphanumeric + hyphen
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


def extract_tenant_slug(
    event: dict[str, Any],
    domains: str | list[str] | None = None,
) -> str | None:
    """
    Extract tenant_slug from API Gateway / Lambda event.

    Args:
        event: Lambda event (API Gateway HTTP API or REST API format)
        domains: Comma-separated base domains or list (e.g. "echo9.net,echo9.ca")

    Returns:
        tenant_slug or None if not found
    """
    domain_list = _parse_domains(domains)

    # 1. X-Tenant-Slug header
    headers = event.get("headers") or {}
    if isinstance(headers, dict):
        # HTTP API: headers are already normalized
        slug = headers.get("x-tenant-slug") or headers.get("X-Tenant-Slug")
    else:
        # REST API: headers can be list of {key, value}
        slug = None
        for h in headers:
            k = h.get("key") or h.get("Key", "")
            if k.lower() == "x-tenant-slug":
                slug = h.get("value") or h.get("Value")
                break

    if slug and _valid_slug(slug):
        return slug.strip().lower()

    # 2. Host header subdomain
    host = headers.get("host") or headers.get("Host") or ""
    if isinstance(host, list):
        host = host[0] if host else ""
    host = str(host).lower()

    # Apex and platform subdomains (app./stage./www./... see reserved_slugs) -> no tenant (T-18)
    platform_hosts = set(domain_list)
    for d in domain_list:
        platform_hosts.update(f"{label}.{d}" for label in RESERVED_SLUGS)
    if host in platform_hosts:
        return None

    # acme.echo9.net or acme.echo9.ca -> acme
    for d in domain_list:
        suffix = f".{d}"
        if host.endswith(suffix):
            subdomain = host[: -len(suffix)]
            if subdomain and _valid_slug(subdomain):
                return subdomain

    # 3. Path parameter: /{tenant}/... or /api/{tenant}/...
    path = event.get("path") or event.get("rawPath") or ""
    path_params = event.get("pathParameters") or {}
    slug = path_params.get("tenant") or path_params.get("tenant_slug")

    if slug and _valid_slug(slug):
        return slug.strip().lower()

    return None


def _parse_domains(domains: str | list[str] | None) -> list[str]:
    """Parse DOMAINS env (comma-separated or list) to list of domain strings."""
    if not domains:
        return ["echo9.net"]
    if isinstance(domains, list):
        return [d.strip() for d in domains if d and isinstance(d, str)]
    return [d.strip() for d in str(domains).split(",") if d.strip()]


def _valid_slug(slug: str) -> bool:
    """Validate slug format: lowercase alphanumeric + hyphen."""
    if not slug or not isinstance(slug, str):
        return False
    s = slug.strip().lower()
    return bool(SLUG_PATTERN.match(s)) and len(s) <= 64


# ---------------------------------------------------------------------------
# Input validation utilities (Task 1.145)
# ---------------------------------------------------------------------------

# Valid statuses for content entities
VALID_CONTENT_STATUSES = frozenset({"DRAFT", "PUBLISHED"})


def parse_json_body(event: dict) -> dict | None:
    """Parse JSON body from Lambda event. Returns None on missing/invalid body."""
    body = event.get("body")
    if not body:
        return None
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None
    return body


def validate_required_fields(body: dict, fields: list[str]) -> str | None:
    """Check that all required fields are present and non-empty strings.

    Returns an error message string if validation fails, None if OK.
    """
    for field in fields:
        val = body.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            return f"{field} is required."
    return None


def validate_slug_format(value: str, field_name: str = "slug") -> str | None:
    """Validate a slug/path value matches the slug pattern.

    Returns error message or None.
    """
    if not value or not isinstance(value, str):
        return f"{field_name} is required."
    s = value.strip().lower()
    if not SLUG_PATTERN.match(s):
        return f"{field_name} must be lowercase alphanumeric + hyphen."
    return None


def validate_content_status(status: str | None) -> str:
    """Normalize and validate a content status value. Returns valid status or 'DRAFT'."""
    if not status:
        return "DRAFT"
    s = str(status).upper()
    return s if s in VALID_CONTENT_STATUSES else "DRAFT"

