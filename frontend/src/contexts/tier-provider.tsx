import { useMemo, type ReactNode } from "react";
import { TierContext, type TierContextValue } from "./tier-context";
import type { FeatureTier } from "@/lib/feature-flags";

export interface TierProviderProps {
  children: ReactNode;
  /** Current tier (default: "free" until Stripe wired) */
  tier?: FeatureTier;
}

export function TierProvider({
  children,
  tier = "free",
}: TierProviderProps) {
  const value = useMemo<TierContextValue>(() => ({ tier }), [tier]);
  return (
    <TierContext.Provider value={value}>{children}</TierContext.Provider>
  );
}
