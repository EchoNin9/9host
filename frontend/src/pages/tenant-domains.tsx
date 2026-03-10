import { useState } from "react"
import { MoreHorizontal, Trash2 } from "lucide-react"
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
import { useTenant } from "@/hooks/use-tenant"
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
          {saving ? "Adding…" : "Add domain"}
        </Button>
      </SheetFooter>
    </form>
  )
}

function DomainsContent() {
  const { tenantSlug } = useTenant()
  const { canEdit } = useTenantRole()
  const { domains, loading, error, add, remove } = useDomains(tenantSlug)
  const { sites } = useSites(tenantSlug)
  const [sheetOpen, setSheetOpen] = useState(false)

  const handleSubmit = async (body: { domain: string; site_id: string }) => {
    return add(body)
  }

  const handleDelete = async (d: Domain) => {
    if (!confirm(`Remove "${d.domain}"? This cannot be undone.`)) return
    await remove(d.domain)
  }

  const handleSheetClose = () => {
    setSheetOpen(false)
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">Loading domains…</p>
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Custom domains</h2>
          <p className="text-sm text-muted-foreground">
            Add custom domains to your sites. Requires Pro or Business tier.
          </p>
        </div>
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
              <CardContent className="pt-0">
                <span
                  className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                    d.status === "verified"
                      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {d.status}
                </span>
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

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Domains</h1>
        <p className="text-muted-foreground">
          Custom domains for {tenantSlug} (Pro+)
        </p>
      </div>

      <FeatureGate
        feature="custom_domains"
        fallback={
          <Card>
            <CardHeader>
              <CardTitle>Custom domains</CardTitle>
              <CardDescription>
                Add custom domains to your sites. Requires Pro or Business tier.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Upgrade to Pro to unlock custom domains.
              </p>
            </CardContent>
          </Card>
        }
      >
        <DomainsContent />
      </FeatureGate>
    </div>
  )
}

export { TenantDomains }
