"""
CloudflareSaaSAdapter (T-07, SPEC §3 Module 1E).

Custom domains are provisioned as Cloudflare for SaaS *custom hostnames* on the
``echo9.net`` zone. The tenant points ``CNAME <domain> -> proxy.echo9.net``; Cloudflare
issues the certificate and the fallback Worker forwards traffic to the public sites
CloudFront distribution with ``X-Forwarded-Host``.

    port = CloudflareSaaSAdapter()                 # credentials from 9host-cloudflare
    rec  = port.register_hostname("myband.com")    # -> CustomHostnameRecord
    rec  = port.get_hostname_status(rec.cf_hostname_id)
    port.delete_hostname(rec.cf_hostname_id)

Credentials (``zone_id``, ``api_token``) come from the ``9host-cloudflare`` Secrets
Manager secret (name/ARN in ``CLOUDFLARE_SECRET_ARN``) via ``secrets_cache``.
The API token is never logged and Cloudflare response bodies are never returned
verbatim to API clients — failures surface as :class:`CloudflareAPIError` with a
safe, client-facing message.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Protocol

logger = logging.getLogger(__name__)

CF_API_BASE = "https://api.cloudflare.com/client/v4"
CNAME_TARGET = "proxy.echo9.net"
DEFAULT_SECRET_ID = "9host-cloudflare"
HTTP_TIMEOUT_SECONDS = 10

# Cloudflare error codes we translate to friendlier client errors.
_CF_DUPLICATE_HOSTNAME_CODES = {1406}
_CF_NOT_FOUND_CODES = {1436, 1414}

_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
_TLD = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$|^xn--[a-z0-9-]+$")
_HOSTNAME_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")

# (method, url, headers, body) -> (status_code, response_bytes)
Transport = Callable[[str, str, dict, bytes | None], tuple[int, bytes]]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class InvalidDomainError(ValueError):
    """The supplied domain is not an acceptable custom hostname."""


class CloudflareAPIError(Exception):
    """A Cloudflare API call failed.

    ``client_message`` is safe to return to API clients; ``cf_code`` / ``cf_message``
    are kept for logs only.
    """

    def __init__(
        self,
        client_message: str,
        *,
        http_status: int = 502,
        cf_code: int | None = None,
        cf_message: str = "",
        kind: str = "upstream_error",
    ):
        super().__init__(client_message)
        self.client_message = client_message
        self.http_status = http_status
        self.cf_code = cf_code
        self.cf_message = cf_message
        self.kind = kind  # "upstream_error" | "duplicate" | "not_found" | "not_configured"

    def to_response_body(self) -> dict:
        body: dict = {"error": self.client_message, "code": f"cloudflare_{self.kind}"}
        if self.cf_code is not None:
            body["cf_error_code"] = self.cf_code
        return body


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CustomHostnameRecord:
    """Normalized view of a Cloudflare custom hostname."""

    cf_hostname_id: str
    domain: str
    status: str  # Cloudflare hostname status: pending | active | moved | blocked | ...
    ssl_status: str  # Cloudflare SSL status: initializing | pending_validation | ... | active
    cname_target: str = CNAME_TARGET
    # DNS records the tenant may add: [{"type": "TXT", "name": ..., "value": ..., "purpose": ...}]
    validation_records: list[dict] = field(default_factory=list)
    verification_errors: list[str] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        """Hostname verified *and* certificate deployed — safe to route traffic."""
        return self.status == "active" and self.ssl_status == "active"

    @property
    def ownership_txt_records(self) -> list[dict]:
        return [r for r in self.validation_records if r.get("purpose") == "ownership"]


class CustomDomainPort(Protocol):
    def register_hostname(self, domain: str) -> CustomHostnameRecord: ...
    def get_hostname_status(self, cf_hostname_id: str) -> CustomHostnameRecord: ...
    def delete_hostname(self, cf_hostname_id: str) -> None: ...


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _platform_domains() -> list[str]:
    raw = os.environ.get("DOMAINS") or "echo9.net,echo9.ca"
    return [d.strip().lower().rstrip(".") for d in raw.split(",") if d.strip()]


def validate_domain(domain: str) -> str:
    """Return the normalized (lowercase, no trailing dot) domain or raise InvalidDomainError."""
    if not isinstance(domain, str):
        raise InvalidDomainError("domain is required.")
    d = domain.strip().lower().rstrip(".")
    if not d:
        raise InvalidDomainError("domain is required.")
    if len(d) > 253:
        raise InvalidDomainError("domain is too long.")
    labels = d.split(".")
    if len(labels) < 2:
        raise InvalidDomainError("domain must be a fully-qualified domain (e.g. example.com).")
    if not all(_LABEL.match(label) for label in labels):
        raise InvalidDomainError("domain must be a valid domain (e.g. example.com, blog.example.com).")
    if not _TLD.match(labels[-1]):
        raise InvalidDomainError("domain must be a valid domain (e.g. example.com, blog.example.com).")
    for platform in _platform_domains():
        if d == platform or d.endswith("." + platform):
            raise InvalidDomainError(f"{platform} subdomains cannot be added as custom domains.")
    return d


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


def urllib_transport(method: str, url: str, headers: dict, body: bytes | None) -> tuple[int, bytes]:
    """Default HTTP transport (stdlib only)."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:  # noqa: S310 - fixed https URL
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        try:
            payload = e.read()
        except Exception:  # noqa: BLE001
            payload = b""
        return e.code, payload


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


def _parse_record(result: dict) -> CustomHostnameRecord:
    ssl = result.get("ssl") or {}
    records: list[dict] = []

    ov = result.get("ownership_verification") or {}
    if ov.get("name") and ov.get("value"):
        records.append({
            "type": (ov.get("type") or "txt").upper(),
            "name": ov["name"],
            "value": ov["value"],
            "purpose": "ownership",
        })
    for vr in ssl.get("validation_records") or []:
        if vr.get("txt_name") and vr.get("txt_value"):
            records.append({
                "type": "TXT",
                "name": vr["txt_name"],
                "value": vr["txt_value"],
                "purpose": "ssl",
            })

    errors: list[str] = []
    for msg in result.get("verification_errors") or []:
        if isinstance(msg, str) and msg:
            errors.append(msg)
    for ve in ssl.get("validation_errors") or []:
        msg = ve.get("message") if isinstance(ve, dict) else ve
        if isinstance(msg, str) and msg:
            errors.append(msg)

    return CustomHostnameRecord(
        cf_hostname_id=str(result.get("id") or ""),
        domain=str(result.get("hostname") or "").lower(),
        status=str(result.get("status") or "pending").lower(),
        ssl_status=str(ssl.get("status") or "initializing").lower(),
        validation_records=records,
        verification_errors=errors,
    )


class CloudflareSaaSAdapter:
    """CustomDomainPort backed by the Cloudflare Custom Hostnames API."""

    def __init__(
        self,
        *,
        zone_id: str | None = None,
        api_token: str | None = None,
        secret_id: str | None = None,
        transport: Transport | None = None,
    ):
        self._zone_id = zone_id
        self._api_token = api_token
        self._secret_id = secret_id
        self._transport = transport or urllib_transport

    # -- credentials ---------------------------------------------------------

    def _credentials(self) -> tuple[str, str]:
        zone_id, token = self._zone_id, self._api_token
        if not (zone_id and token):
            from secrets_cache import get_secret_json

            secret_id = self._secret_id or os.environ.get("CLOUDFLARE_SECRET_ARN") or DEFAULT_SECRET_ID
            data = get_secret_json(secret_id) or {}
            zone_id = zone_id or str(data.get("zone_id") or "").strip()
            token = token or str(data.get("api_token") or "").strip()
        if not zone_id or not token or token == "REPLACE_ME":
            raise CloudflareAPIError(
                "Custom domains are not configured. Contact support.",
                http_status=503,
                kind="not_configured",
            )
        return zone_id, token

    # -- HTTP ------------------------------------------------------------------

    def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
        zone_id, token = self._credentials()
        url = f"{CF_API_BASE}/zones/{zone_id}/custom_hostnames{path}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        try:
            status, raw = self._transport(method, url, headers, body)
        except Exception as exc:  # noqa: BLE001 - network errors
            logger.warning("cloudflare_saas: %s %s transport error: %s", method, path or "/", type(exc).__name__)
            raise CloudflareAPIError("Could not reach the custom domain provider. Try again later.") from None

        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}

        if 200 <= status < 300 and data.get("success", True):
            return data

        errs = data.get("errors") or []
        first = errs[0] if errs and isinstance(errs[0], dict) else {}
        cf_code = first.get("code") if isinstance(first.get("code"), int) else None
        cf_message = str(first.get("message") or "")[:300]
        logger.warning(
            "cloudflare_saas: %s %s failed: http=%s cf_code=%s cf_message=%s",
            method, path or "/", status, cf_code, cf_message,
        )
        if cf_code in _CF_DUPLICATE_HOSTNAME_CODES or status == 409:
            raise CloudflareAPIError(
                "This domain is already registered with the custom domain provider.",
                http_status=409, cf_code=cf_code, cf_message=cf_message, kind="duplicate",
            )
        if cf_code in _CF_NOT_FOUND_CODES or status == 404:
            raise CloudflareAPIError(
                "Custom hostname not found.",
                http_status=404, cf_code=cf_code, cf_message=cf_message, kind="not_found",
            )
        if status in (401, 403):
            raise CloudflareAPIError(
                "Custom domain provider rejected our credentials. Contact support.",
                http_status=502, cf_code=cf_code, cf_message=cf_message,
            )
        if status == 400 or status == 422:
            raise CloudflareAPIError(
                "The custom domain provider rejected this domain.",
                http_status=400, cf_code=cf_code, cf_message=cf_message, kind="rejected",
            )
        raise CloudflareAPIError(
            "Custom domain provider error. Try again later.",
            http_status=502, cf_code=cf_code, cf_message=cf_message,
        )

    @staticmethod
    def _check_id(cf_hostname_id: str) -> str:
        if not cf_hostname_id or not _HOSTNAME_ID.match(cf_hostname_id):
            raise CloudflareAPIError("Invalid custom hostname id.", http_status=400, kind="rejected")
        return cf_hostname_id

    # -- CustomDomainPort --------------------------------------------------------

    def register_hostname(self, domain: str) -> CustomHostnameRecord:
        hostname = validate_domain(domain)
        payload = {
            "hostname": hostname,
            "ssl": {
                "method": "http",
                "type": "dv",
                "settings": {"min_tls_version": "1.2"},
            },
        }
        data = self._call("POST", "", payload)
        return _parse_record(data.get("result") or {})

    def get_hostname_status(self, cf_hostname_id: str) -> CustomHostnameRecord:
        data = self._call("GET", f"/{self._check_id(cf_hostname_id)}")
        return _parse_record(data.get("result") or {})

    def delete_hostname(self, cf_hostname_id: str) -> None:
        try:
            self._call("DELETE", f"/{self._check_id(cf_hostname_id)}")
        except CloudflareAPIError as e:
            if e.kind == "not_found":
                return  # idempotent: already gone
            raise
