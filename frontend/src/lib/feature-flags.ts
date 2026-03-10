/**
 * FeatureFlag utility for tier-based feature gating.
 * Tiers: Free, Pro, Business.
 * Pro unlocks: Custom Domains, Advanced Analytics.
 * Business: same + future features.
 */

export type FeatureTier = "free" | "pro" | "business";

/** Feature keys aligned with saas-architecture.mdc */
export type FeatureKey = "custom_domains" | "advanced_analytics";

const TIER_ORDER: FeatureTier[] = ["free", "pro", "business"];

function tierRank(tier: FeatureTier): number {
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
