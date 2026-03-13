# 9host Feature Tiers

| Tier | Custom Domains | Advanced Analytics | Payment | Assignable by |
|------|----------------|-------------------|---------|---------------|
| Free | ❌ | ❌ | — | superadmin |
| Pro | ✅ | ✅ | Stripe | superadmin, checkout |
| Business | ✅ | ✅ (+ more) | Stripe | superadmin, checkout |
| VIP | ✅ | ✅ (+ more) | — | superadmin only |

## VIP Tier

VIP = Business features, no payment. Friends & family use case.

- **Features:** Same as Business (custom domains, advanced analytics, etc.)
- **Assignment:** Only superadmin can assign VIP via create tenant or administer tenant
- **Billing:** VIP excluded from Stripe. Never show checkout/portal for VIP tenants
- **Visibility:** Non-VIP users do not see VIP tier exists (frontend hides it outside superadmin)

## Extensibility

Backend uses `api/tier_config.py`:

- `VALID_TIERS` — all valid tier values
- `TIER_FEATURE_RANK` — rank for tier comparison (higher = more features)
- `PAYABLE_TIERS` — tiers that can be purchased via Stripe (excludes VIP)
- `tier_rank(tier)` — numeric rank for comparison
- `tier_has_feature(tier, feature)` — check if tier grants feature
- `is_valid_tier(tier)` — validation
- `is_payable_tier(tier)` — whether tier is Stripe-purchasable
