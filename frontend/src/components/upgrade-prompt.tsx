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
import { getRequiredTier } from "@/lib/feature-flags"

const FEATURE_LABELS: Record<FeatureKey, { title: string; description: string }> = {
  custom_domains: {
    title: "Custom domains",
    description: "Add custom domains to your sites. Requires Pro or Business tier.",
  },
  advanced_analytics: {
    title: "Advanced Analytics",
    description: "View page views, visitors, and top pages. Requires Pro or Business tier.",
  },
}

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
