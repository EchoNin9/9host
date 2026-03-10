/**
 * Tier context: provides current subscription tier for feature gating.
 * Defaults to "free" until Stripe integration (agent3 task 3.2) wires subscription status.
 */

import { createContext } from "react";
import type { FeatureTier } from "@/lib/feature-flags";

export interface TierContextValue {
  /** Current subscription tier */
  tier: FeatureTier;
}

export const TierContext = createContext<TierContextValue | null>(null);
