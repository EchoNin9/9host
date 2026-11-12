import { useState } from "react"
import { GlobeLock, Loader2, MoreHorizontal, Plus, Settings2, ShieldCheck, Trash2 } from "lucide-react"
import { Card } from "@/components/ui/card"
import { NativeSelect } from "@/components/ui/native-select"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { ModuleLocked } from "@/components/module-locked"
import { EmptyState, FormField, LoadingState, Notice } from "@/components/page"
import { DomainStatusBadge } from "@/components/status-badges"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
  SheetDescription,
} from "@/components/ui/sheet"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { FeatureGate } from "@/components/feature-gate"
import { DomainSetupGuideDialog } from "@/components/domain-setup-guide"
import { useTenantMetadata } from "@/hooks/use-tenant-metadata"
import { useTenantRole } from "@/hooks/use-tenant-role"
import { useDomains } from "@/hooks/use-domains"
import { useSites } from "@/hooks/use-sites"
import type { Domain } from "@/lib/api"
import { TenantPage, TenantPageHeader } from "@/components/tenant-page"

function DomainForm({
  onSubmit,
  onClose,
  sites,
}: {
  onSubmit: (body: { domain: string; site_id: string }) => Promise<Domain>
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
      await onSubmit({ domain: d, site_id: siteId })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add domain. Check format (e.g. example.com) or try again.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <FormField label="Domain" htmlFor="domain" hint="An apex domain (example.com) or a subdomain (blog.example.com).">
        <Input
          id="domain"
          type="text"
          inputMode="url"
          autoCapitalize="none"
          spellCheck={false}
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="example.com"
          className="font-mono"
          required
          autoFocus
        />
      </FormField>
      <FormField label="Serves site" htmlFor="site">
        <NativeSelect id="site" value={siteId} onChange={(e) => setSiteId(e.target.value)} required>
          <option value="">Select a site</option>
          {sites.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </NativeSelect>
      </FormField>
      {error && <Notice tone="danger">{error}</Notice>}
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
  const { canEdit } = useTenantRole()
  const { domains, loading, error, add, remove, activate, polling } = useDomains()
  const { sites } = useSites()
  const [sheetOpen, setSheetOpen] = useState(false)
  const [setupDomain, setSetupDomain] = useState<Domain | null>(null)
  const [activating, setActivating] = useState<string | null>(null)
  const [activateError, setActivateError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Domain | null>(null)

  const handleSubmit = async (body: { domain: string; site_id: string }) => {
    const result = await add(body)
    if (result) {
      setSheetOpen(false)
      setSetupDomain(result)
    }
    return result
  }


  const handleActivate = async (d: Domain) => {
    setActivating(d.domain)
    setActivateError(null)
    try {
      const result = await activate(d.domain)
      setSetupDomain({
        ...result.domain,
        validation_records: result.validation_records ?? result.domain.validation_records,
      })
    } catch (e) {
      setActivateError(
        e instanceof Error ? e.message : "Status check failed. Check DNS records and try again."
      )
    } finally {
      setActivating(null)
    }
  }

  const handleSheetClose = () => {
    setSheetOpen(false)
  }

  const canActivate = (d: Domain) => d.status === "PENDING_VALIDATION"

  const header = (
    <TenantPageHeader
      title="Domains"
      description={
        <>
          Serve a site from your own domain. Each domain needs a CNAME to{" "}
          <span className="font-mono text-foreground">proxy.echonin9.com</span> plus the validation records we show you.
        </>
      }
      actions={
        <>
          {polling && (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground" role="status">
              <Loader2 className="size-3 animate-spin" aria-hidden />
              Checking status…
            </span>
          )}
          {canEdit && (
            <Button
              onClick={() => setSheetOpen(true)}
              disabled={sites.length === 0}
              title={sites.length === 0 ? "Create a site first" : undefined}
            >
              <Plus className="size-4" />
              Add domain
            </Button>
          )}
        </>
      }
    />
  )

  return (
    <>
      {header}

      {activateError && <Notice tone="danger">{activateError}</Notice>}

      {setupDomain && (
        <DomainSetupGuideDialog
          domain={setupDomain}
          open={!!setupDomain}
          onOpenChange={(open) => !open && setSetupDomain(null)}
        />
      )}

      <Sheet open={sheetOpen} onOpenChange={(open) => setSheetOpen(open)}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Add custom domain</SheetTitle>
            <SheetDescription>Next, we show the DNS records to add at your registrar.</SheetDescription>
          </SheetHeader>
          <DomainForm onSubmit={handleSubmit} onClose={handleSheetClose} sites={sites} />
        </SheetContent>
      </Sheet>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={`Remove ${deleteTarget?.domain ?? "domain"}?`}
        description="The domain stops serving your site. You can add it again later, but DNS validation starts over."
        confirmLabel="Remove domain"
        pendingLabel="Removing…"
        onConfirm={async () => {
          if (deleteTarget) await remove(deleteTarget.domain)
        }}
      />

      {loading ? (
        <LoadingState label="Loading domains…" rows={2} />
      ) : error ? (
        <Notice tone="danger">{error}</Notice>
      ) : domains.length === 0 ? (
        <EmptyState
          icon={GlobeLock}
          title="No custom domains yet"
          description={
            sites.length === 0
              ? "Create a site first, then point your domain at it."
              : "Add a domain you own and point it at one of your sites."
          }
          action={
            canEdit &&
            sites.length > 0 && (
              <Button onClick={() => setSheetOpen(true)}>
                <Plus className="size-4" />
                Add domain
              </Button>
            )
          }
        />
      ) : (
        <Card className="gap-0 py-0">
          <ul className="divide-y">
            {domains.map((d) => (
              <li key={d.domain} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-mono text-sm font-medium">{d.domain}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    Serves {sites.find((s) => s.id === d.site_id)?.name ?? d.site_id}
                  </p>
                </div>
                <DomainStatusBadge status={d.status} />
                <div className="flex items-center gap-1">
                  {canEdit && canActivate(d) && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleActivate(d)}
                      disabled={activating === d.domain}
                    >
                      {activating === d.domain ? (
                        <Loader2 className="size-4 animate-spin" aria-hidden />
                      ) : (
                        <ShieldCheck className="size-4" aria-hidden />
                      )}
                      {activating === d.domain ? "Checking…" : "Check status"}
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => setSetupDomain(d)}>
                    <Settings2 className="size-4" />
                    DNS records
                  </Button>
                  {canEdit && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon-sm">
                          <MoreHorizontal className="size-4" />
                          <span className="sr-only">More actions for {d.domain}</span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem variant="destructive" onSelect={() => setDeleteTarget(d)}>
                          <Trash2 className="size-4" />
                          Remove domain
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  )
}

function DomainsLocked() {
  return (
    <>
      <TenantPageHeader title="Domains" description="Serve a site from your own domain." />
      <ModuleLocked feature="custom_domains" />
    </>
  )
}

function TenantDomains() {
  const { tenant } = useTenantMetadata()
  const isVip = (tenant?.tier?.toLowerCase() ?? "") === "vip"

  return (
    <TenantPage>
      {isVip ? (
        <DomainsContent />
      ) : (
        <FeatureGate feature="custom_domains" fallback={<DomainsLocked />}>
          <DomainsContent />
        </FeatureGate>
      )}
    </TenantPage>
  )
}

export { TenantDomains }
