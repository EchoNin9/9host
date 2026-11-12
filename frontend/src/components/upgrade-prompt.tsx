/**
 * UpgradePrompt: shown when a feature is locked by tier.
 * Links to billing/checkout for upgrade.
 */

import { Link } from "react-router-dom"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import type { FeatureKey } from "@/lib/feature-flags"
import { getRequiredTier, isBillingEnabled } from "@/lib/feature-flags"
import { FEATURE_LABELS } from "@/lib/feature-labels"


export interface UpgradePromptProps {
  /** Feature that is locked */
  feature?: FeatureKey
  /** Optional custom title */
  title?: string
  /** Optional custom description */
  description?: string
}

/**
 * Renders a card prompting the user to upgrade, with a link to billing/checkout.
 */
export function UpgradePrompt({
  feature,
  title,
  description,
}: UpgradePromptProps) {
  if (!isBillingEnabled()) {
    return null
  }

  const tier = feature ? getRequiredTier(feature) : "pro"
  const labels = feature ? FEATURE_LABELS[feature] : null
  const displayTitle = title ?? labels?.title ?? "Upgrade required"
  const displayDesc =
    description ?? labels?.description ?? `Upgrade to ${tier} to unlock this feature.`

  return (
    <Card>
      <CardHeader>
        <CardTitle>{displayTitle}</CardTitle>
        <CardDescription>{displayDesc}</CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild>
          <Link to="../settings">Upgrade plan</Link>
        </Button>
      </CardContent>
    </Card>
  )
}
