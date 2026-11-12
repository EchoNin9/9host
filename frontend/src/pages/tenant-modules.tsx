/**
 * Module Marketplace (cPanel-style) — Task 2.79, 2.89
 * Dedicated Modules/Apps dashboard with grid of toggles.
 * Reuses tenant-settings module_overrides logic.
 * Task 2.89: add updates/blog, events_shows, media_gallery, branding.
 */

import { useState } from "react"
import {
  Globe,
  BarChart3,
  FileText,
  Calendar,
  Image,
  Palette,
} from "lucide-react"
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
import { useTenantScope } from "@/context/tenant-scope-context"
import { useTenantRole } from "@/hooks/use-tenant-role"
import { useTenantMetadata } from "@/hooks/use-tenant-metadata"
import { UpgradePrompt } from "@/components/upgrade-prompt"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { LoadingState } from "@/components/page"
import { TierBadge } from "@/components/status-badges"
import { TenantPage, TenantPageHeader } from "@/components/tenant-page"
import { cn } from "@/lib/utils"
import {
  ALL_MODULE_KEYS,
  getRequiredTier,
  isBillingEnabled,
  type FeatureKey,
} from "@/lib/feature-flags"

const MODULE_META: Record<
  FeatureKey,
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
  updates_blog: {
    title: "Updates / Blog",
    description: "Blog posts and news updates. Add a blog section to your site.",
    icon: FileText,
  },
  events_shows: {
    title: "Events & Shows",
    description: "Events, tour dates, and shows. Display upcoming dates and venues.",
    icon: Calendar,
  },
  media_gallery: {
    title: "Media Gallery",
    description: "Image gallery and media library. Upload and manage images for your site.",
    icon: Image,
  },
  branding: {
    title: "Branding",
    description: "Logo, colors, fonts, and favicon. Customize your site's look and feel.",
    icon: Palette,
  },
}

const TIER_ORDER = ["free", "pro", "business", "vip"] as const
type TierSlug = (typeof TIER_ORDER)[number]

/** VIP has same rank as business (Task 2.83). */
function tierRank(t: string): number {
  const lower = t.toLowerCase()
  if (lower === "vip") return 2
  const i = TIER_ORDER.indexOf(lower as TierSlug)
  return i >= 0 ? i : -1
}

function TenantModules() {
  const { tenantSlug } = useTenant()
  const { api } = useTenantScope()
  const { canEdit } = useTenantRole()
  const { tenant, loading, refetch } = useTenantMetadata()
  const [savingKey, setSavingKey] = useState<string | null>(null)

  const currentTier = (tenant?.tier?.toLowerCase() ?? "free") as TierSlug

  const handleToggle = async (key: FeatureKey, value: boolean) => {
    if (!tenantSlug || !tenant || !canEdit) return
    setSavingKey(key)
    const token = await getToken()
    const next = { ...(tenant.module_overrides ?? {}), [key]: value }
    const result = await patchTenantModuleOverrides(api, token, next)
    setSavingKey(null)
    if (result) void refetch()
  }

  return (
    <TenantPage>
      <TenantPageHeader
        title="Modules"
        description="Turn site features on or off for this tenant. Some modules are part of a higher tier."
        meta={<TierBadge tier={tenant?.tier} />}
      />

      {loading ? (
        <LoadingState label="Loading modules…" />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {ALL_MODULE_KEYS.map((key) => {
            const meta = MODULE_META[key]
            const Icon = meta.icon
            const requiredTier = getRequiredTier(key)
            const tierUnlocked =
              currentTier === "vip" ||
              tierRank(currentTier) >= tierRank(requiredTier)
            const enabled =
              tenant?.resolved_features?.[key] ??
              tenant?.module_overrides?.[key] ??
              false
            const isSaving = savingKey === key
            const switchId = `module-${key}`
            const locked = !tierUnlocked && !enabled

            return (
              <Card
                key={key}
                className="gap-3"
              >
                <CardHeader className="flex flex-row items-start gap-3">
                  <span
                    className={cn(
                      "flex size-9 shrink-0 items-center justify-center rounded-md border",
                      enabled ? "border-primary/25 bg-brand-muted text-primary" : "bg-muted text-muted-foreground"
                    )}
                  >
                    <Icon className="size-4" aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1 space-y-1">
                    <CardTitle>
                      <label htmlFor={switchId}>{meta.title}</label>
                    </CardTitle>
                    {requiredTier !== "free" && (
                      <Badge mono tone={tierUnlocked ? "neutral" : "warning"}>
                        {requiredTier}+
                      </Badge>
                    )}
                  </div>
                  {!locked && canEdit && (
                    <Switch
                      id={switchId}
                      checked={enabled}
                      onCheckedChange={(v) => handleToggle(key, v)}
                      disabled={isSaving}
                      aria-describedby={`${switchId}-desc`}
                    />
                  )}
                </CardHeader>
                <CardContent className="flex flex-1 flex-col gap-3">
                  <CardDescription id={`${switchId}-desc`}>{meta.description}</CardDescription>
                  {locked ? (
                    isBillingEnabled() ? (
                      <UpgradePrompt feature={key} />
                    ) : (
                      <p className="mt-auto text-xs text-muted-foreground">
                        Part of the {requiredTier.charAt(0).toUpperCase() + requiredTier.slice(1)} tier. A platform
                        admin can change your plan.
                      </p>
                    )
                  ) : (
                    <p className="mt-auto text-xs text-muted-foreground" aria-live="polite">
                      {isSaving ? "Saving…" : enabled ? "On" : "Off"}
                      {!canEdit && " · view only"}
                    </p>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </TenantPage>
  )
}

export { TenantModules }
