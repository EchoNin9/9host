/**
 * HOC: wraps a component so it only renders when the feature is enabled.
 * Aligns with saas-architecture.mdc FeatureGate usage.
 */

import type { FeatureKey } from "@/lib/feature-flags";
import { useFeatureGate } from "@/hooks/use-tier";

export function withFeatureGate<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  feature: FeatureKey,
  Fallback?: React.ComponentType
) {
  function WithFeatureGateComponent(props: P) {
    const enabled = useFeatureGate(feature);
    if (!enabled) {
      return Fallback ? <Fallback /> : null;
    }
    return <WrappedComponent {...props} />;
  }
  WithFeatureGateComponent.displayName = `withFeatureGate(${
    WrappedComponent.displayName ?? WrappedComponent.name ?? "Component"
  })`;
  return WithFeatureGateComponent;
}
