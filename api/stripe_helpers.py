"""
Stripe helpers for 9host billing (Task 3.1).
Fetches config from Secrets Manager (cached via secrets_cache), provides Stripe client.
"""

import os

import secrets_cache


def _get_stripe_config() -> dict | None:
    """Stripe config from Secrets Manager (5-minute module cache, Bug #7)."""
    return secrets_cache.get_secret_json(os.environ.get("STRIPE_SECRET_ARN"))


def get_stripe_api_key() -> str | None:
    """Stripe secret key for API calls."""
    cfg = _get_stripe_config()
    return (cfg or {}).get("secret_key") or None


def get_stripe_webhook_secret() -> str | None:
    """Webhook signing secret for verifying Stripe events."""
    cfg = _get_stripe_config()
    return (cfg or {}).get("webhook_secret") or None


def get_stripe_price_id(tier: str) -> str | None:
    """Stripe Price ID for tier (pro, business)."""
    cfg = _get_stripe_config()
    if not cfg:
        return None
    t = (tier or "").lower()
    if t == "pro":
        return cfg.get("price_pro")
    if t == "business":
        return cfg.get("price_business")
    return None


def stripe_configured() -> bool:
    """True if Stripe is configured (secret_key and at least one price)."""
    key = get_stripe_api_key()
    if not key or not key.startswith("sk_"):
        return False
    if not get_stripe_price_id("pro") and not get_stripe_price_id("business"):
        return False
    return True
