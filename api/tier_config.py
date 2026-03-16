"""
Tier configuration for 9host (Task 1.82).

Centralizes tier definitions for extensibility. VIP = Business features, no payment.
Only superadmin assigns VIP. VIP excluded from billing/Stripe.
"""

# All valid tiers
VALID_TIERS = ("FREE", "PRO", "BUSINESS", "VIP")

# Tiers that can be purchased via Stripe (VIP excluded)
PAYABLE_TIERS = ("PRO", "BUSINESS")

# Feature rank: FREE=0, PRO=1, BUSINESS=2, VIP=2 (same as Business)
TIER_FEATURE_RANK = {
    "FREE": 0,
    "PRO": 1,
    "BUSINESS": 2,
    "VIP": 2,
}


def tier_rank(tier: str) -> int:
    """Tier rank for comparison. FREE=0, PRO=1, BUSINESS=2, VIP=2."""
    t = (tier or "FREE").upper()
    return TIER_FEATURE_RANK.get(t, 0)


# Feature keys aligned with frontend feature-flags.ts
FEATURE_KEYS = ("custom_domains", "advanced_analytics")

# Content module keys (Task 1.94): updates/blog, events_shows, media_gallery, branding
CONTENT_MODULE_KEYS = ("updates_blog", "events_shows", "media_gallery", "branding")

# All module keys (features + content modules) for resolved_features
ALL_MODULE_KEYS = FEATURE_KEYS + CONTENT_MODULE_KEYS

# Minimum tier for content modules. FREE=0, PRO=1, BUSINESS=2
CONTENT_MODULE_TIER = {
    "updates_blog": "FREE",
    "events_shows": "FREE",
    "media_gallery": "PRO",
    "branding": "FREE",
}


def tier_has_feature(tier: str, feature: str) -> bool:
    """Check if tier grants feature by default (Pro+ for custom_domains, advanced_analytics)."""
    if feature not in FEATURE_KEYS:
        return False
    return tier_rank(tier) >= 1  # PRO, BUSINESS, VIP


def module_tier_required(module_key: str) -> str:
    """Minimum tier for content module. Returns FREE, PRO, or BUSINESS."""
    return CONTENT_MODULE_TIER.get(module_key, "FREE")


def tier_has_module(tier: str, module_key: str) -> bool:
    """Check if tier grants content module by default."""
    if module_key not in CONTENT_MODULE_KEYS:
        return False
    required = module_tier_required(module_key)
    return tier_rank(tier) >= tier_rank(required)


def is_valid_tier(tier: str) -> bool:
    """Check if tier is valid."""
    return (tier or "").upper() in VALID_TIERS


def is_payable_tier(tier: str) -> bool:
    """Check if tier can be purchased via Stripe (VIP is not payable)."""
    return (tier or "").upper() in PAYABLE_TIERS


def tiers_with_pro_features() -> tuple[str, ...]:
    """Tiers that have Pro+ features (custom domains, advanced analytics)."""
    return ("PRO", "BUSINESS", "VIP")


# Per-tier upload limits (bytes) — Task 1.88. MVP: 10 MB per file for all tiers.
# Cumulative quota enforcement deferred to post-MVP.
UPLOAD_LIMIT_BYTES = {
    "FREE": 10 * 1024 * 1024,      # 10 MB
    "PRO": 10 * 1024 * 1024,       # 10 MB
    "BUSINESS": 10 * 1024 * 1024,  # 10 MB
    "VIP": 10 * 1024 * 1024,       # 10 MB
}


def upload_limit_bytes(tier: str) -> int:
    """Max bytes per single upload for tier. Used for pre-signed POST content-length-range."""
    t = (tier or "FREE").upper()
    return UPLOAD_LIMIT_BYTES.get(t, 10 * 1024 * 1024)
