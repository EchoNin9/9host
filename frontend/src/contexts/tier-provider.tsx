import { useMemo, type ReactNode } from "react";
import { TierContext, type TierContextValue } from "./tier-context";
import type { FeatureTier } from "@/lib/feature-flags";
import type { ResolvedFeatures } from "@/lib/api";

export interface TierProviderProps {
  children: ReactNode;
  /** Current tier (default: "free" until Stripe wired) */
  tier?: FeatureTier;
  /** Resolved features from GET /api/tenant (Task 2.18). Overrides tier for FeatureGate. */
  resolved_features?: ResolvedFeatures;
}

export function TierProvider({
  children,
  tier = "free",
  resolved_features,
}: TierProviderProps) {
  const value = useMemo<TierContextValue>(
    () => ({ tier: tier as FeatureTier, resolved_features }),
    [tier, resolved_features]
  );
  return (
    <TierContext.Provider value={value}>{children}</TierContext.Provider>
  );
}
