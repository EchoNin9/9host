"use client"

import { useState } from "react"
import { NativeSelect } from "@/components/ui/native-select"
import { Link, useNavigate } from "react-router-dom"
import { fetchAuthSession } from "aws-amplify/auth"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Input } from "@/components/ui/input"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { useImpersonation } from "@/hooks/use-impersonation"
import {
  createAdminTenant,
  deleteAdminTenant,
  getToken,
} from "@/lib/api"
import { Building2, MoreHorizontal, Plus, Search, Trash2, UserCog } from "lucide-react"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState, FormField, LoadingState, Notice, Page, PageHeader } from "@/components/page"
import { TierBadge } from "@/components/status-badges"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

function CreateTenantSheet({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: () => void
}) {
  const [slug, setSlug] = useState("")
  const [name, setName] = useState("")
  const [tier, setTier] = useState("FREE")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSlugChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value.toLowerCase().replace(/\s/g, "-").replace(/[^a-z0-9-]/g, "")
    setSlug(v.slice(0, 60))
  }

  const handleCreate = async () => {
    setError(null)
    const s = slug.trim()
    if (!s) {
      setError("Slug is required")
      return
    }
    if (s.length > 60) {
      setError("Slug must be at most 60 characters")
      return
    }
    if (!/^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/.test(s)) {
      setError("Slug must be lowercase alphanumeric and hyphen (e.g. acme-corp)")
      return
    }
    setSaving(true)
    const token = await getToken()
    const result = await createAdminTenant(token, {
      slug: s,
      name: name.trim() || s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      tier,
    })
    setSaving(false)
    if (result) {
      onCreated()
      onClose()
    } else {
      setError("Failed to create tenant")
    }
  }

  return (
    <form
      className="flex flex-1 flex-col gap-5"
      onSubmit={(e) => {
        e.preventDefault()
        void handleCreate()
      }}
    >
      <FormField
        label="Slug"
        htmlFor="admin-new-slug"
        hint={
          <>
            Lowercase letters, numbers, hyphens. Max 60. Address:{" "}
            <span className="font-mono text-foreground">{slug || "acme-corp"}.echo9.net</span>
          </>
        }
      >
        <Input
          id="admin-new-slug"
          value={slug}
          onChange={handleSlugChange}
          placeholder="acme-corp"
          maxLength={60}
          className="font-mono"
          required
          autoFocus
        />
      </FormField>
      <FormField label="Display name" htmlFor="admin-new-name" hint="Defaults to the slug in title case.">
        <Input
          id="admin-new-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Acme Corp"
        />
      </FormField>
      <FormField label="Tier" htmlFor="admin-new-tier">
        <NativeSelect id="admin-new-tier" value={tier} onChange={(e) => setTier(e.target.value)}>
          <option value="FREE">Free</option>
          <option value="PRO">Pro</option>
          <option value="BUSINESS">Business</option>
          <option value="VIP">VIP</option>
        </NativeSelect>
      </FormField>
      {error && <Notice tone="danger">{error}</Notice>}
      <SheetFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? "Creating…" : "Create tenant"}
        </Button>
      </SheetFooter>
    </form>
  )
}

function SuperadminTenantsPage() {
  const { tenants, loading, refetch } = useAdminTenants()
  const { setImpersonate } = useImpersonation()
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteSlug, setDeleteSlug] = useState<string | null>(null)
  const [query, setQuery] = useState("")

  const handleDelete = async () => {
    if (!deleteSlug) return false
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const ok = await deleteAdminTenant(token, deleteSlug)
    if (ok) void refetch()
    return ok
  }

  const handleImpersonate = (slug: string) => {
    setImpersonate(slug)
    navigate(`/${slug}`)
  }

  const q = query.trim().toLowerCase()
  const filtered = q
    ? tenants.filter((t) => t.slug.includes(q) || (t.name ?? "").toLowerCase().includes(q))
    : tenants

  return (
    <Page>
      <PageHeader
        eyebrow="Platform"
        title="Tenants"
        description="Every tenant on the platform. Administer to edit settings, users, sites and domains."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" />
            New tenant
          </Button>
        }
      />

      <Card className="gap-0 py-0">
        <div className="flex flex-wrap items-center gap-3 border-b px-5 py-3">
          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search name or slug"
              aria-label="Search tenants"
              className="pl-9"
            />
          </div>
          <p className="tabular ml-auto text-xs text-muted-foreground" aria-live="polite">
            {loading ? "" : `${filtered.length} of ${tenants.length}`}
          </p>
        </div>
        {loading ? (
          <LoadingState className="p-5" label="Loading tenants…" />
        ) : tenants.length === 0 ? (
          <EmptyState className="m-5" icon={Building2} title="No tenants yet" />
        ) : filtered.length === 0 ? (
          <p className="px-5 py-8 text-center text-sm text-muted-foreground">No tenants match “{query}”.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Tenant</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead className="text-right">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((t) => (
                <TableRow key={t.slug}>
                  <TableCell>
                    <Link to={`/admin/tenants/${t.slug}`} className="group block min-w-0 rounded-sm">
                      <span className="block font-medium group-hover:underline">{t.name || t.slug}</span>
                      <span className="block font-mono text-xs text-muted-foreground">{t.slug}</span>
                    </Link>
                  </TableCell>
                  <TableCell>
                    <TierBadge tier={t.tier} />
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap">
                    <Button size="sm" variant="outline" asChild>
                      <Link to={`/admin/tenants/${t.slug}`}>Administer</Link>
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button size="icon-sm" variant="ghost" className="ml-1">
                          <MoreHorizontal className="size-4" />
                          <span className="sr-only">More actions for {t.slug}</span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => handleImpersonate(t.slug)}>
                          <UserCog className="size-4" />
                          Impersonate
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem variant="destructive" onSelect={() => setDeleteSlug(t.slug)}>
                          <Trash2 className="size-4" />
                          Delete tenant
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <Sheet open={createOpen} onOpenChange={setCreateOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>New tenant</SheetTitle>
            <SheetDescription>Pick a slug and a starting tier. You can change the tier and owner later.</SheetDescription>
          </SheetHeader>
          <CreateTenantSheet
            key={createOpen ? "open" : "closed"}
            onClose={() => setCreateOpen(false)}
            onCreated={() => void refetch()}
          />
        </SheetContent>
      </Sheet>

      <ConfirmDialog
        open={!!deleteSlug}
        onOpenChange={(o) => !o && setDeleteSlug(null)}
        title={`Delete tenant “${deleteSlug ?? ""}”?`}
        description="This permanently deletes the tenant and all its sites, domains, users, and settings. This action cannot be undone."
        confirmLabel="Delete tenant"
        onConfirm={handleDelete}
      />
    </Page>
  )
}

export { SuperadminTenantsPage }
