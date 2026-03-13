/**
 * FeatureFlag utility for tier-based feature gating.
 * Tiers: Free, Pro, Business, VIP (Task 2.83).
 * Pro unlocks: Custom Domains, Advanced Analytics.
 * Business: same + future features.
 * VIP: Business features, no payment. Superadmin only. Never shown in billing/upgrade.
 */

export type FeatureTier = "free" | "pro" | "business" | "vip";

/** Feature keys aligned with saas-architecture.mdc */
export type FeatureKey = "custom_domains" | "advanced_analytics";

/** Tiers that can be purchased via Stripe. VIP excluded (Task 1.82). */
export const PAYABLE_TIERS = ["pro", "business"] as const;

const TIER_ORDER: FeatureTier[] = ["free", "pro", "business", "vip"];

/** VIP has same feature rank as business (Task 2.83). */
function tierRank(tier: FeatureTier): number {
  if (tier === "vip") return 2; // same as business
  const i = TIER_ORDER.indexOf(tier);
  return i >= 0 ? i : -1;
}

function tierMeetsOrExceeds(tier: FeatureTier, required: FeatureTier): boolean {
  return tierRank(tier) >= tierRank(required);
}

/** Minimum tier required for each feature */
const FEATURE_TIERS: Record<FeatureKey, FeatureTier> = {
  custom_domains: "pro",
  advanced_analytics: "pro",
};

/**
 * Check if a feature is enabled for the given tier.
 */
export function hasFeature(tier: FeatureTier, feature: FeatureKey): boolean {
  const required = FEATURE_TIERS[feature];
  return required ? tierMeetsOrExceeds(tier, required) : false;
}

/**
 * Get the minimum tier required for a feature.
 */
export function getRequiredTier(feature: FeatureKey): FeatureTier {
  return FEATURE_TIERS[feature] ?? "free";
}
