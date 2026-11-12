import { useState, useEffect, type ReactNode } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { getToken } from "@/lib/api"
import {
  createBillingCheckout,
  createBillingPortal,
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
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { NativeSelect } from "@/components/ui/native-select"
import { FormField, LoadingState, Notice } from "@/components/page"
import { TierBadge } from "@/components/status-badges"
import { TenantPage, TenantPageHeader } from "@/components/tenant-page"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantScope } from "@/context/tenant-scope-context"
import { useTenantRole } from "@/hooks/use-tenant-role"
import { useTenantMetadata } from "@/hooks/use-tenant-metadata"
import { useTenantUsers } from "@/hooks/use-tenant-users"
import { useAuth } from "@/hooks/use-auth"
import { Crown, CreditCard, Settings2 } from "lucide-react"

import { isBillingEnabled } from "@/lib/feature-flags"

const TIER_ORDER = ["free", "pro", "business", "vip"] as const
type TierSlug = (typeof TIER_ORDER)[number]

/** VIP has same rank as business. Payable tiers: pro, business only. */
function tierRank(t: string): number {
  const lower = t.toLowerCase()
  if (lower === "vip") return 2
  const i = TIER_ORDER.indexOf(lower as TierSlug)
  return i >= 0 ? i : -1
}

function Row({ label, children, action }: { label: string; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 py-3.5 sm:flex-row sm:items-center sm:gap-6">
      <dt className="w-40 shrink-0 text-sm text-muted-foreground">{label}</dt>
      <dd className="flex min-w-0 flex-1 items-center gap-3 text-sm">
        <div className="min-w-0 flex-1">{children}</div>
        {action}
      </dd>
    </div>
  )
}

function TenantSettings() {
  const { tenantSlug, tenantBasePath } = useTenant()
  const base = tenantBasePath || `/${tenantSlug}`
  const { api } = useTenantScope()
  const { role, canEdit } = useTenantRole()
  const { tenant, loading, refetch } = useTenantMetadata()
  const { users } = useTenantUsers()
  const { userId } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [transferOpen, setTransferOpen] = useState(false)
  const [transferTarget, setTransferTarget] = useState("")
  const [transferring, setTransferring] = useState(false)
  const [transferError, setTransferError] = useState<string | null>(null)
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

  const handleTransfer = async () => {
    if (!tenantSlug || !transferTarget) return
    setTransferring(true)
    setTransferError(null)
    const token = await getToken()
    const ok = await putTransferOwner(api, token, transferTarget)
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
    const result = await createBillingCheckout(api, token, {
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
    const result = await createBillingPortal(api, token, {
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
    <TenantPage>
      <TenantPageHeader title="Settings" description="Tenant details, ownership and plan." />

      {isBillingEnabled() && checkoutMessage && (
        <Notice tone={checkoutMessage.includes("success") ? "success" : "warning"}>{checkoutMessage}</Notice>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Tenant settings</CardTitle>
          <CardDescription>
            {canEdit ? "General information about this tenant." : `View-only access (${role})`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <LoadingState rows={2} />
          ) : (
            <dl className="divide-y border-t">
              <Row label="Name">{tenant?.name || tenantSlug}</Row>
              <Row label="Slug">
                <span className="font-mono">{tenantSlug}</span>
              </Row>
              <Row label="Plan">
                <TierBadge tier={tenant?.tier} />
              </Row>
              <Row label="Your role">
                <span className="capitalize">{role}</span>
              </Row>
              {tenant?.owner_sub && (
                <Row
                  label="Owner"
                  action={
                    isOwner &&
                    canEdit && (
                      <Button variant="outline" size="sm" onClick={() => setTransferOpen(true)}>
                        Transfer
                      </Button>
                    )
                  }
                >
                  <span className="inline-flex items-center gap-2">
                    <Crown className="size-4 text-warning" aria-hidden />
                    {isOwner ? "You" : <span className="font-mono text-xs">{tenant.owner_sub.slice(0, 8)}…</span>}
                  </span>
                </Row>
              )}
              {canEdit && (
                <Row
                  label="Modules"
                  action={
                    <Button asChild variant="outline" size="sm">
                      <Link to={`${base}/modules`}>
                        <Settings2 className="size-4" />
                        Manage
                      </Link>
                    </Button>
                  }
                >
                  <span className="text-muted-foreground">Blog, events, media, branding and more.</span>
                </Row>
              )}
            </dl>
          )}
        </CardContent>
      </Card>

      {isBillingEnabled() && (
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
              <LoadingState rows={1} />
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Current tier:</span>
                  <TierBadge tier={currentTier} />
                </div>
                {currentTier === "vip" && (
                  <p className="text-sm text-muted-foreground">
                    VIP — Full features, no billing required.
                  </p>
                )}
                {billingError && <Notice tone="danger">{billingError}</Notice>}
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
                        variant={tierRank(currentTier) < tierRank("pro") ? "outline" : "default"}
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
      )}

      <Sheet open={transferOpen} onOpenChange={setTransferOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Transfer ownership</SheetTitle>
            <SheetDescription>
              The new owner gets full control of this tenant. You stay on as an admin.
            </SheetDescription>
          </SheetHeader>
          <div className="flex flex-1 flex-col gap-5">
            <FormField label="New owner" htmlFor="transfer-target">
              <NativeSelect
                id="transfer-target"
                value={transferTarget}
                onChange={(e) => setTransferTarget(e.target.value)}
              >
                <option value="">Select a member</option>
                {users
                  .filter((u) => u.sub !== userId)
                  .map((u) => (
                    <option key={u.sub} value={u.sub}>
                      {u.name || u.email || u.sub}
                    </option>
                  ))}
              </NativeSelect>
            </FormField>
            {transferError && <Notice tone="danger">{transferError}</Notice>}
            <SheetFooter>
              <Button variant="outline" onClick={() => setTransferOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleTransfer}
                disabled={!transferTarget || transferring}
              >
                {transferring ? "Transferring…" : "Transfer ownership"}
              </Button>
            </SheetFooter>
          </div>
        </SheetContent>
      </Sheet>
    </TenantPage>
  )
}

export { TenantSettings }
