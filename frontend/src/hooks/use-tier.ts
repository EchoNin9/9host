import { useContext } from "react";
import { TierContext } from "@/contexts/tier-context";
import { hasFeature as hasFeatureUtil, type FeatureKey, type FeatureTier } from "@/lib/feature-flags";

export function useTier(): FeatureTier {
  const ctx = useContext(TierContext);
  return ctx?.tier ?? "free";
}

/**
 * Check if the current tier has access to a feature.
 */
export function useFeatureGate(feature: FeatureKey): boolean {
  const tier = useTier();
  return hasFeatureUtil(tier, feature);
}
