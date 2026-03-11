import { useContext } from "react";
import { TierContext } from "@/contexts/tier-context";
import { hasFeature as hasFeatureUtil, type FeatureKey, type FeatureTier } from "@/lib/feature-flags";

export function useTier(): FeatureTier {
  const ctx = useContext(TierContext);
  return ctx?.tier ?? "free";
}

/**
 * Check if the current tier has access to a feature.
 * Uses resolved_features when present (Task 2.18); otherwise tier-based.
 */
export function useFeatureGate(feature: FeatureKey): boolean {
  const ctx = useContext(TierContext);
  return useFeatureGateInternal(ctx, feature);
}

export function useFeatureGateInternal(
  ctx: { tier?: FeatureTier; resolved_features?: Record<string, boolean> } | null,
  feature: FeatureKey
): boolean {
  if (ctx?.resolved_features && feature in ctx.resolved_features) {
    return Boolean(ctx.resolved_features[feature]);
  }
  const tier = (ctx?.tier ?? "free") as FeatureTier;
  return hasFeatureUtil(tier, feature);
}
