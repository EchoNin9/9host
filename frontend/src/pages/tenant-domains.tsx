import { useState } from "react"
import { MoreHorizontal, Trash2, Settings2, ShieldCheck, Loader2 } from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/ui/sheet"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { FeatureGate } from "@/components/feature-gate"
import { DomainSetupGuideDialog } from "@/components/domain-setup-guide"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantMetadata } from "@/hooks/use-tenant-metadata"
import { useTenantRole } from "@/hooks/use-tenant-role"
import { useDomains } from "@/hooks/use-domains"
import { useSites } from "@/hooks/use-sites"
import type { Domain } from "@/lib/api"

function DomainForm({
  onSubmit,
  onClose,
  sites,
}: {
  onSubmit: (body: { domain: string; site_id: string }) => Promise<Domain | null>
  onClose: () => void
  sites: { id: string; name: string }[]
}) {
  const [domain, setDomain] = useState("")
  const [siteId, setSiteId] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const d = domain.trim().toLowerCase()
    if (!d || !siteId) return
    setSaving(true)
    setError(null)
    try {
      const result = await onSubmit({ domain: d, site_id: siteId })
      if (result) onClose()
      else setError("Failed to add domain. Check format (e.g. example.com) or try again.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label htmlFor="domain" className="text-sm font-medium">
          Domain
        </label>
        <Input
          id="domain"
          type="text"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="example.com"
          required
          className="mt-1"
        />
        <p className="mt-1 text-xs text-muted-foreground">
          e.g. example.com or blog.example.com
        </p>
      </div>
      <div>
        <label htmlFor="site" className="text-sm font-medium">
          Site
        </label>
        <select
          id="site"
          value={siteId}
          onChange={(e) => setSiteId(e.target.value)}
          required
          className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
        >
          <option value="">Select a site</option>
          {sites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>
      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}
      <SheetFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? "Adding..." : "Add domain"}
        </Button>
      </SheetFooter>
    </form>
  )
}

function StatusBadge({ status }: { status: string }) {
  const s = status?.toUpperCase() ?? "PENDING"
  if (s === "ACTIVE") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400">
        Active
      </span>
    )
  }
  if (s === "PENDING_VALIDATION") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
        <Loader2 className="size-3 animate-spin" />
        Validating SSL
      </span>
    )
  }
  if (s === "VERIFIED") {
    return (
      <span className="inline-flex rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
        Verified
      </span>
    )
  }
  return (
    <span className="inline-flex rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
      {status || "Pending"}
    </span>
  )
}

function DomainsContent() {
  const { tenantSlug } = useTenant()
  const { canEdit } = useTenantRole()
  const { domains, loading, error, add, remove, activate, polling } = useDomains(tenantSlug)
  const { sites } = useSites(tenantSlug)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [setupDomain, setSetupDomain] = useState<Domain | null>(null)
  const [activating, setActivating] = useState<string | null>(null)
  const [activateError, setActivateError] = useState<string | null>(null)

  const handleSubmit = async (body: { domain: string; site_id: string }) => {
    const result = await add(body)
    if (result) {
      setSheetOpen(false)
      setSetupDomain(result)
    }
    return result
  }

  const handleDelete = async (d: Domain) => {
    if (!confirm(`Remove "${d.domain}"? This cannot be undone.`)) return
    await remove(d.domain)
  }

  const handleActivate = async (d: Domain) => {
    setActivating(d.domain)
    setActivateError(null)
    try {
      const result = await activate(d.domain)
      if (result) {
        // Show setup guide with ACM validation records
        setSetupDomain(result.domain)
      }
    } catch (e) {
      setActivateError(
        e instanceof Error ? e.message : "Activation failed. Check DNS records and try again."
      )
    } finally {
      setActivating(null)
    }
  }

  const handleSheetClose = () => {
    setSheetOpen(false)
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">Loading domains...</p>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    )
  }

  const canActivate = (d: Domain) => {
    const s = d.status?.toUpperCase() ?? ""
    return s === "PENDING" || s === "VERIFIED" || s === ""
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Custom domains</h2>
          <p className="text-sm text-muted-foreground">
            Add custom domains to your sites. Requires Pro or Business tier.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {polling && (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              Checking status...
            </span>
          )}
          {canEdit && (
            <Button
              onClick={() => setSheetOpen(true)}
              disabled={sites.length === 0}
              title={sites.length === 0 ? "Create a site first" : undefined}
            >
              Add domain
            </Button>
          )}
        </div>
      </div>

      {activateError && (
        <Card>
          <CardContent className="pt-4">
            <p className="text-sm text-destructive">{activateError}</p>
          </CardContent>
        </Card>
      )}

      {setupDomain && (
        <DomainSetupGuideDialog
          domain={setupDomain}
          open={!!setupDomain}
          onOpenChange={(open) => !open && setSetupDomain(null)}
        />
      )}

      <Sheet
        open={sheetOpen}
        onOpenChange={(open) => setSheetOpen(open)}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Add custom domain</SheetTitle>
          </SheetHeader>
          <div className="mt-4">
            <DomainForm
              onSubmit={handleSubmit}
              onClose={handleSheetClose}
              sites={sites}
            />
          </div>
        </SheetContent>
      </Sheet>

      {domains.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              No custom domains yet. Add a domain to point it at one of your sites.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {domains.map((d) => (
            <Card key={d.domain}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 py-4">
                <div>
                  <CardTitle className="text-base">{d.domain}</CardTitle>
                  <CardDescription>
                    Site: {sites.find((s) => s.id === d.site_id)?.name ?? d.site_id}
                  </CardDescription>
                </div>
                {canEdit && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="size-8">
                        <MoreHorizontal className="size-4" />
                        <span className="sr-only">Actions</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => setSetupDomain(d)}>
                        <Settings2 className="mr-2 size-4" />
                        DNS setup
                      </DropdownMenuItem>
                      {canActivate(d) && (
                        <DropdownMenuItem
                          onClick={() => handleActivate(d)}
                          disabled={activating === d.domain}
                        >
                          <ShieldCheck className="mr-2 size-4" />
                          {activating === d.domain ? "Activating..." : "Activate SSL"}
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem
                        variant="destructive"
                        onClick={() => handleDelete(d)}
                      >
                        <Trash2 className="mr-2 size-4" />
                        Remove
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </CardHeader>
              <CardContent className="pt-0 flex items-center justify-between">
                <StatusBadge status={d.status} />
                <div className="flex items-center gap-2">
                  {canEdit && canActivate(d) && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => handleActivate(d)}
                      disabled={activating === d.domain}
                    >
                      {activating === d.domain ? (
                        <>
                          <Loader2 className="mr-1 size-3 animate-spin" />
                          Activating...
                        </>
                      ) : (
                        <>
                          <ShieldCheck className="mr-1 size-3" />
                          Activate SSL
                        </>
                      )}
                    </Button>
                  )}
                  {(d.verification_cname_target || d.verification_txt_record || (d.acm_validation_records?.length ?? 0) > 0) && (
                    <Button
                      variant="link"
                      size="sm"
                      className="h-auto p-0 text-xs"
                      onClick={() => setSetupDomain(d)}
                    >
                      DNS setup
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

function TenantDomains() {
  const { tenantSlug } = useTenant()
  const { tenant } = useTenantMetadata(tenantSlug)
  const isVip = (tenant?.tier?.toLowerCase() ?? "") === "vip"

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Domains</h1>
        <p className="text-muted-foreground">
          Custom domains for {tenantSlug} (Pro+)
        </p>
      </div>

      {isVip ? (
        <DomainsContent />
      ) : (
        <FeatureGate feature="custom_domains">
          <DomainsContent />
        </FeatureGate>
      )}
    </div>
  )
}

export { TenantDomains }
