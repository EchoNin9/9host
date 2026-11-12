/**
 * FeatureGate fallback for a module that is off for this tenant. With billing enabled it is the
 * UpgradePrompt; with billing disabled it explains where the module is switched on, with no
 * pricing or upgrade CTA (BillingFeatureFlag).
 */

import { Link } from "react-router-dom"
import { Lock } from "lucide-react"

import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/page"
import { UpgradePrompt } from "@/components/upgrade-prompt"
import { FEATURE_LABELS } from "@/lib/feature-labels"
import { useTenantScope } from "@/context/tenant-scope-context"
import { getRequiredTier, hasFeature, isBillingEnabled, type FeatureKey } from "@/lib/feature-flags"
import { useTier } from "@/hooks/use-tier"
import { useTenantRole } from "@/hooks/use-tenant-role"

export function ModuleLocked({ feature }: { feature: FeatureKey }) {
  const { basePath, embedded } = useTenantScope()
  const { canEdit } = useTenantRole()
  const tier = useTier()
  if (isBillingEnabled()) return <UpgradePrompt feature={feature} />
  const title = FEATURE_LABELS[feature].title
  const required = getRequiredTier(feature)
  // Tier-locked modules can't be switched on by the tenant (PATCH /api/tenant rejects them).
  const tierAllows = tier === "vip" || hasFeature(tier, feature)
  const requiredLabel = required.charAt(0).toUpperCase() + required.slice(1)
  return (
    <EmptyState
      icon={Lock}
      title={`${title} is not enabled`}
      description={
        tierAllows
          ? `Turn on ${title} in ${embedded ? "the tenant settings" : "Modules"} to use it on this tenant.`
          : `${title} is part of the ${requiredLabel} tier. Ask a platform admin to change this tenant's plan.`
      }
      action={
        canEdit &&
        (tierAllows || embedded) && (
          <Button asChild variant="outline" size="sm">
            <Link to={embedded ? basePath : `${basePath}/modules`}>{embedded ? "Open tenant settings" : "Open Modules"}</Link>
          </Button>
        )
      }
    />
  )
}
