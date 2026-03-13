"use client"

import { type ReactNode } from "react"
import { TierProvider } from "@/contexts/tier-provider"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantMetadata } from "@/hooks/use-tenant-metadata"

/**
 * Fetches tenant metadata and provides tier + resolved_features to TierContext (Task 2.18).
 * When in tenant context, FeatureGate uses resolved_features from GET /api/tenant.
 */
export function TenantTierProvider({ children }: { children: ReactNode }) {
  const { tenantSlug } = useTenant()
  const { tenant } = useTenantMetadata(tenantSlug)

  const tier = (tenant?.tier?.toLowerCase() ?? "free") as "free" | "pro" | "business" | "vip"
  const resolved_features = tenant?.resolved_features

  return (
    <TierProvider tier={tier} resolved_features={resolved_features}>
      {children}
    </TierProvider>
  )
}
