/**
 * FeatureGate: wraps premium UI elements. Pro+ tier unlocks custom_domains, advanced_analytics.
 * Aligns with saas-architecture.mdc: <FeatureGate feature="custom_domains"> or <FeatureGate feature="advanced_analytics">
 * When locked, shows UpgradePrompt by default (links to billing/checkout).
 */

import type { ReactNode } from "react";
import type { FeatureKey } from "@/lib/feature-flags";
import { isBillingEnabled } from "@/lib/feature-flags";
import { useFeatureGate } from "@/hooks/use-tier";
import { UpgradePrompt } from "@/components/upgrade-prompt";

export interface FeatureGateProps {
  /** Feature to gate (Pro+ tier required) */
  feature: FeatureKey;
  /** Content to show when feature is enabled */
  children: ReactNode;
  /** Optional fallback when feature is disabled. Defaults to UpgradePrompt when billing is enabled. */
  fallback?: ReactNode;
}

/**
 * Renders children only when the current tier has access to the feature.
 * When locked:
 * - If billing is enabled, shows UpgradePrompt (or custom fallback) with link to billing.
 * - If billing is disabled, gates the feature without showing upgrade CTA / pricing link.
 */
export function FeatureGate({ feature, children, fallback }: FeatureGateProps) {
  const enabled = useFeatureGate(feature);
  if (enabled) {
    return <>{children}</>;
  }
  if (!isBillingEnabled()) {
    // When billing is disabled, gate the feature itself but do not show upgrade CTA / pricing link
    return fallback ? <>{fallback}</> : null;
  }
  const lockedFallback = fallback ?? <UpgradePrompt feature={feature} />;
  return <>{lockedFallback}</>;
}
