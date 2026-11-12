"""
Module-level Secrets Manager cache (T-02, Bug #7).

Warm Lambda containers reuse secrets for ``TTL_SECONDS`` instead of calling
``secretsmanager:GetSecretValue`` on every request. Used for ``9host-jwt-secret``,
``9host-stripe``, ``9host-cloudns`` and ``9host-cloudflare``.

    get_secret_string(secret_id) -> str | None   # raw SecretString (e.g. JWT signing key)
    get_secret_json(secret_id)   -> dict | None  # parsed JSON SecretString

Both return ``None`` when ``secret_id`` is empty or the fetch fails. Failures are not
cached, so a transient Secrets Manager error is retried on the next call.
"""

from __future__ import annotations

import json
import logging
import threading
import time

logger = logging.getLogger(__name__)

TTL_SECONDS = 300  # 5 minutes

# Patchable seams for tests.
_clock = time.monotonic

_lock = threading.Lock()
_cache: dict[str, tuple[float, str]] = {}  # secret_id -> (expires_at, SecretString)


def _fetch_secret_string(secret_id: str) -> str | None:
    """Fetch the raw SecretString from AWS Secrets Manager."""
    import boto3

    client = boto3.client("secretsmanager")
    resp = client.get_secret_value(SecretId=secret_id)
    return resp.get("SecretString")


def get_secret_string(secret_id: str | None) -> str | None:
    """Return the (stripped) SecretString for ``secret_id``, cached for 5 minutes."""
    if not secret_id:
        return None
    now = _clock()
    with _lock:
        hit = _cache.get(secret_id)
        if hit and hit[0] > now:
            return hit[1]
    try:
        value = _fetch_secret_string(secret_id)
    except Exception as exc:  # noqa: BLE001 - never crash callers on secret fetch failure
        logger.warning("secrets_cache: failed to fetch secret %s: %s", secret_id, exc)
        return None
    value = (value or "").strip()
    if not value:
        return None
    with _lock:
        _cache[secret_id] = (now + TTL_SECONDS, value)
    return value


def get_secret_json(secret_id: str | None) -> dict | None:
    """Return the SecretString for ``secret_id`` parsed as a JSON object, or None."""
    raw = get_secret_string(secret_id)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("secrets_cache: secret %s is not valid JSON", secret_id)
        return None
    return data if isinstance(data, dict) else None


def clear_cache() -> None:
    """Drop all cached secrets (tests / forced rotation)."""
    with _lock:
        _cache.clear()
