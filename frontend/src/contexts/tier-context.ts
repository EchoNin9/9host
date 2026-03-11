/**
 * Tier context: provides current subscription tier for feature gating.
 * resolved_features (from GET /api/tenant) overrides tier-based checks when present (Task 2.18).
 */

import { createContext } from "react";
import type { FeatureTier } from "@/lib/feature-flags";
import type { ResolvedFeatures } from "@/lib/api";

export interface TierContextValue {
  /** Current subscription tier */
  tier: FeatureTier;
  /** Resolved features (tier + module_overrides). When present, use instead of tier for FeatureGate. */
  resolved_features?: ResolvedFeatures
}

export const TierContext = createContext<TierContextValue | null>(null);
