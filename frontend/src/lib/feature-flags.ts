/**
 * FeatureFlag utility for tier-based feature gating.
 * Tiers: Free, Pro, Business, VIP (Task 2.83).
 * Pro unlocks: Custom Domains, Advanced Analytics.
 * Business: same + future features.
 * VIP: Business features, no payment. Superadmin only. Never shown in billing/upgrade.
 */

export type FeatureTier = "free" | "pro" | "business" | "vip";

/** Feature keys aligned with saas-architecture.mdc (Task 2.89: + content modules) */
export type FeatureKey =
  | "custom_domains"
  | "advanced_analytics"
  | "updates_blog"
  | "events_shows"
  | "media_gallery"
  | "branding";

/** All module keys for tenant-modules grid */
export const ALL_MODULE_KEYS: FeatureKey[] = [
  "custom_domains",
  "advanced_analytics",
  "updates_blog",
  "events_shows",
  "media_gallery",
  "branding",
];

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

/** Minimum tier required for each feature (Task 2.89: WEB_HOSTING_PLAN Module Reference) */
const FEATURE_TIERS: Record<FeatureKey, FeatureTier> = {
  custom_domains: "pro",
  advanced_analytics: "pro",
  updates_blog: "free",
  events_shows: "free",
  media_gallery: "pro",
  branding: "free",
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
