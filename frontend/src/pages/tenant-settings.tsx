import { useState, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { getToken } from "@/lib/api"
import {
  createBillingCheckout,
  createBillingPortal,
  patchTenantModuleOverrides,
  putTransferOwner,
} from "@/lib/api"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantRole } from "@/hooks/use-tenant-role"
import { useTenantMetadata } from "@/hooks/use-tenant-metadata"
import { useTenantUsers } from "@/hooks/use-tenant-users"
import { useAuth } from "@/hooks/use-auth"
import { Crown, CreditCard, Settings2 } from "lucide-react"

const FEATURE_KEYS = ["custom_domains", "advanced_analytics"] as const

const TIER_ORDER = ["free", "pro", "business"] as const
type TierSlug = (typeof TIER_ORDER)[number]

function tierRank(t: string): number {
  const i = TIER_ORDER.indexOf(t.toLowerCase() as TierSlug)
  return i >= 0 ? i : -1
}

function TenantSettings() {
  const { tenantSlug } = useTenant()
  const { role, canEdit } = useTenantRole()
  const { tenant, loading, refetch } = useTenantMetadata(tenantSlug)
  const { users } = useTenantUsers(tenantSlug)
  const { userId } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [transferOpen, setTransferOpen] = useState(false)
  const [transferTarget, setTransferTarget] = useState("")
  const [transferring, setTransferring] = useState(false)
  const [transferError, setTransferError] = useState<string | null>(null)
  const [moduleOverridesSaving, setModuleOverridesSaving] = useState(false)
  const [billingLoading, setBillingLoading] = useState<string | null>(null)
  const [billingError, setBillingError] = useState<string | null>(null)
  const [checkoutMessage, setCheckoutMessage] = useState<string | null>(null)

  const isOwner = tenant?.owner_sub && userId && tenant.owner_sub === userId
  const currentTier = (tenant?.tier?.toLowerCase() ?? "free") as TierSlug

  useEffect(() => {
    const status = searchParams.get("checkout")
    if (status === "success") {
      setCheckoutMessage("Subscription updated successfully.")
      setSearchParams({}, { replace: true })
      void refetch()
    } else if (status === "cancel") {
      setCheckoutMessage("Checkout cancelled.")
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, setSearchParams, refetch])

  const handleModuleOverrideToggle = async (
    key: string,
    value: boolean
  ) => {
    if (!tenantSlug || !tenant) return
    const next = { ...(tenant.module_overrides ?? {}), [key]: value }
    setModuleOverridesSaving(true)
    const token = await getToken()
    const result = await patchTenantModuleOverrides(
      tenantSlug,
      token,
      next
    )
    setModuleOverridesSaving(false)
    if (result) void refetch()
  }

  const handleTransfer = async () => {
    if (!tenantSlug || !transferTarget) return
    setTransferring(true)
    setTransferError(null)
    const token = await getToken()
    const ok = await putTransferOwner(tenantSlug, token, transferTarget)
    setTransferring(false)
    if (ok) {
      setTransferOpen(false)
      setTransferTarget("")
      void refetch()
    } else {
      setTransferError("Transfer failed. API may not be available yet.")
    }
  }

  const baseUrl = typeof window !== "undefined" ? window.location.origin : ""
  const settingsPath = tenantSlug ? `/${tenantSlug}/settings` : "/settings"

  const handleUpgrade = async (tier: "pro" | "business") => {
    if (!tenantSlug || !canEdit) return
    setBillingLoading(tier)
    setBillingError(null)
    const token = await getToken()
    const result = await createBillingCheckout(tenantSlug, token, {
      tier,
      success_url: `${baseUrl}${settingsPath}?checkout=success`,
      cancel_url: `${baseUrl}${settingsPath}?checkout=cancel`,
    })
    setBillingLoading(null)
    if (result.ok) {
      window.location.href = result.url
    } else {
      setBillingError(result.error)
    }
  }

  const handleManageBilling = async () => {
    if (!tenantSlug || !canEdit) return
    setBillingLoading("portal")
    setBillingError(null)
    const token = await getToken()
    const result = await createBillingPortal(tenantSlug, token, {
      return_url: `${baseUrl}${settingsPath}`,
    })
    setBillingLoading(null)
    if (result.ok) {
      window.location.href = result.url
    } else {
      setBillingError(result.error)
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-muted-foreground">
          Configure {tenantSlug}
        </p>
      </div>

      {checkoutMessage && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            checkoutMessage.includes("success")
              ? "border-green-500/30 bg-green-500/10 text-green-700 dark:text-green-400"
              : "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400"
          }`}
        >
          {checkoutMessage}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard className="size-4" />
            Billing
          </CardTitle>
          <CardDescription>
            Manage your subscription and tier
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Current tier:</span>
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    currentTier === "business"
                      ? "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-300"
                      : currentTier === "pro"
                        ? "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300"
                        : "bg-muted text-muted-foreground"
                  }`}
                >
                  {currentTier.charAt(0).toUpperCase() + currentTier.slice(1)}
                </span>
              </div>
              {billingError && (
                <p className="text-sm text-destructive">{billingError}</p>
              )}
              {canEdit && (
                <div className="flex flex-wrap gap-2">
                  {tierRank(currentTier) < tierRank("pro") && (
                    <Button
                      variant="default"
                      size="sm"
                      disabled={!!billingLoading}
                      onClick={() => handleUpgrade("pro")}
                    >
                      {billingLoading === "pro" ? "Redirecting…" : "Upgrade to Pro"}
                    </Button>
                  )}
                  {tierRank(currentTier) < tierRank("business") && (
                    <Button
                      variant="default"
                      size="sm"
                      disabled={!!billingLoading}
                      onClick={() => handleUpgrade("business")}
                    >
                      {billingLoading === "business"
                        ? "Redirecting…"
                        : "Upgrade to Business"}
                    </Button>
                  )}
                  {tierRank(currentTier) >= tierRank("pro") && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!!billingLoading}
                      onClick={handleManageBilling}
                    >
                      {billingLoading === "portal"
                        ? "Opening…"
                        : "Manage billing"}
                    </Button>
                  )}
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tenant settings</CardTitle>
          <CardDescription>
            {canEdit
              ? "Manage your tenant configuration"
              : `View-only access (${role})`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <>
              {tenant?.owner_sub && (
                <div className="flex items-center gap-2 rounded-lg border p-3">
                  <Crown className="size-4 text-amber-500" />
                  <div>
                    <p className="text-sm font-medium">Account owner</p>
                    <p className="text-xs text-muted-foreground">
                      {isOwner
                        ? "You are the owner"
                        : `Owner: ${tenant.owner_sub.slice(0, 8)}…`}
                    </p>
                  </div>
                  {isOwner && canEdit && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="ml-auto"
                      onClick={() => setTransferOpen(true)}
                    >
                      Transfer owner
                    </Button>
                  )}
                </div>
              )}
              {canEdit && (
                <div className="rounded-lg border p-3">
                  <p className="text-sm font-medium flex items-center gap-2">
                    <Settings2 className="size-4" />
                    Module overrides
                  </p>
                  <p className="text-xs text-muted-foreground mb-2">
                    Override tier-based features (e.g. Free + custom domains)
                  </p>
                  <div className="space-y-2">
                    {FEATURE_KEYS.map((key) => (
                      <label
                        key={key}
                        className="flex items-center gap-2 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={
                            tenant?.resolved_features?.[key] ??
                            tenant?.module_overrides?.[key] ??
                            false
                          }
                          onChange={(e) =>
                            handleModuleOverrideToggle(key, e.target.checked)
                          }
                          disabled={moduleOverridesSaving}
                          className="h-4 w-4 rounded"
                        />
                        <span className="text-sm capitalize">
                          {key.replace("_", " ")}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Sheet open={transferOpen} onOpenChange={setTransferOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Transfer ownership</SheetTitle>
          </SheetHeader>
          <div className="mt-4 space-y-4">
            <p className="text-sm text-muted-foreground">
              Transfer this tenant to another member. You will become a regular
              admin.
            </p>
            <div>
              <label className="text-sm font-medium">New owner</label>
              <select
                value={transferTarget}
                onChange={(e) => setTransferTarget(e.target.value)}
                className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
              >
                <option value="">Select user</option>
                {users
                  .filter((u) => u.sub !== userId)
                  .map((u) => (
                    <option key={u.sub} value={u.sub}>
                      {u.name || u.email || u.sub}
                    </option>
                  ))}
              </select>
            </div>
            {transferError && (
              <p className="text-sm text-destructive">{transferError}</p>
            )}
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setTransferOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleTransfer}
                disabled={!transferTarget || transferring}
              >
                {transferring ? "Transferring…" : "Transfer"}
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}

export { TenantSettings }
