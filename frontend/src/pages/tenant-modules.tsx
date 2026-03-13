/**
 * Module Marketplace (cPanel-style) — Task 2.79
 * Dedicated Modules/Apps dashboard with grid of toggles.
 * Reuses tenant-settings module_overrides logic.
 */

import { useState } from "react"
import { Link } from "react-router-dom"
import { Package, Globe, BarChart3 } from "lucide-react"
import { getToken } from "@/lib/api"
import { patchTenantModuleOverrides } from "@/lib/api"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantRole } from "@/hooks/use-tenant-role"
import { useTenantMetadata } from "@/hooks/use-tenant-metadata"
import { UpgradePrompt } from "@/components/upgrade-prompt"
import { getRequiredTier, type FeatureKey } from "@/lib/feature-flags"

const FEATURE_KEYS = ["custom_domains", "advanced_analytics"] as const

const MODULE_META: Record<
  (typeof FEATURE_KEYS)[number],
  { title: string; description: string; icon: typeof Globe }
> = {
  custom_domains: {
    title: "Custom Domains",
    description: "Add custom domains to your sites. Point your domain to Echo9 and manage DNS.",
    icon: Globe,
  },
  advanced_analytics: {
    title: "Advanced Analytics",
    description: "View page views, unique visitors, and top pages over time.",
    icon: BarChart3,
  },
}

const TIER_ORDER = ["free", "pro", "business"] as const
type TierSlug = (typeof TIER_ORDER)[number]

function tierRank(t: string): number {
  const i = TIER_ORDER.indexOf(t.toLowerCase() as TierSlug)
  return i >= 0 ? i : -1
}

function TenantModules() {
  const { tenantSlug } = useTenant()
  const { canEdit } = useTenantRole()
  const { tenant, loading, refetch } = useTenantMetadata(tenantSlug)
  const [savingKey, setSavingKey] = useState<string | null>(null)

  const currentTier = (tenant?.tier?.toLowerCase() ?? "free") as TierSlug

  const handleToggle = async (key: FeatureKey, value: boolean) => {
    if (!tenantSlug || !tenant || !canEdit) return
    setSavingKey(key)
    const token = await getToken()
    const next = { ...(tenant.module_overrides ?? {}), [key]: value }
    const result = await patchTenantModuleOverrides(tenantSlug, token, next)
    setSavingKey(null)
    if (result) void refetch()
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <Package className="size-6" />
          Modules
        </h1>
        <p className="text-muted-foreground">
          Enable or disable features for {tenantSlug}. Some require a higher tier.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURE_KEYS.map((key) => {
            const meta = MODULE_META[key]
            const Icon = meta.icon
            const requiredTier = getRequiredTier(key)
            const tierUnlocked = tierRank(currentTier) >= tierRank(requiredTier)
            const enabled =
              tenant?.resolved_features?.[key] ??
              tenant?.module_overrides?.[key] ??
              false
            const isSaving = savingKey === key

            return (
              <Card key={key} className="flex flex-col">
                <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                  <div className="flex items-center gap-2">
                    <Icon className="size-5 text-muted-foreground" />
                    <CardTitle className="text-base">{meta.title}</CardTitle>
                  </div>
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      requiredTier === "business"
                        ? "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300"
                        : requiredTier === "pro"
                          ? "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
                          : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {requiredTier}
                  </span>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col gap-4">
                  <CardDescription>{meta.description}</CardDescription>
                  {!tierUnlocked && !enabled ? (
                    <UpgradePrompt feature={key} />
                  ) : canEdit ? (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">
                        {enabled ? "Enabled" : "Disabled"}
                      </span>
                      <label className="relative inline-flex cursor-pointer items-center">
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={(e) =>
                            handleToggle(key, e.target.checked)
                          }
                          disabled={isSaving}
                          className="peer sr-only"
                        />
                        <div className="peer h-6 w-11 rounded-full bg-muted after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-muted-foreground/20 after:bg-background after:transition-all after:content-[''] peer-checked:bg-primary peer-checked:after:translate-x-full peer-checked:after:border-primary peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-ring peer-disabled:cursor-not-allowed peer-disabled:opacity-50" />
                      </label>
                    </div>
                  ) : (
                    <span className="text-sm text-muted-foreground">
                      {enabled ? "Enabled" : "Disabled"} (view-only)
                    </span>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      <p className="text-sm text-muted-foreground">
        Module overrides are also available in{" "}
        <Link to="../settings" className="text-primary hover:underline">
          Settings
        </Link>
        .
      </p>
    </div>
  )
}

export { TenantModules }
