import { useState, useCallback, useEffect } from "react"
import { NativeSelect } from "@/components/ui/native-select"
import { Link, Navigate, useNavigate, useParams } from "react-router-dom"
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Switch } from "@/components/ui/switch"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState, FormField, LoadingState, Notice, Page, PageHeader } from "@/components/page"
import { TierBadge } from "@/components/status-badges"
import { cn } from "@/lib/utils"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { useImpersonation } from "@/hooks/use-impersonation"
import { useTenantUsers } from "@/hooks/use-tenant-users"
import { TenantScopeProvider } from "@/context/tenant-scope"
import { TenantTierProvider } from "@/contexts/tenant-tier-provider"
import { TenantSites } from "@/pages/tenant-sites"
import { TenantDomains } from "@/pages/tenant-domains"
import { TenantUsers } from "@/pages/tenant-users"
import { SiteContentEditor } from "@/pages/site-content-editor"
import {
  fetchAdminTenant,
  deleteAdminTenant,
  getToken,
  putAdminTenantSettings,
  type AdminTenantDetail,
} from "@/lib/api"
import { Building2, Globe, GlobeLock, MoreHorizontal, Settings, Trash2, UserCog, Users } from "lucide-react"

import { ALL_MODULE_KEYS } from "@/lib/feature-flags"

const DEFAULT_MODULE_OVERRIDES: Record<string, boolean> = Object.fromEntries(
  ALL_MODULE_KEYS.map((k) => [k, false])
)

const TABS = [
  { id: "settings", label: "Settings", icon: Settings },
  { id: "users", label: "Users", icon: Users },
  { id: "sites", label: "Sites", icon: Globe },
  { id: "domains", label: "Domains", icon: GlobeLock },
] as const

/**
 * Superadmin console for one tenant (/admin/tenants/:slug[/:tab]).
 * Sites, domains, users and the content editor are the tenant dashboard's own
 * views, scoped to this tenant with superadmin impersonation.
 */
function AdministerTenantPage() {
  const { slug, tab = "settings", siteId } = useParams<{ slug: string; tab?: string; siteId?: string }>()
  const navigate = useNavigate()
  const { isSuperadmin, loading: superadminLoading } = useAdminTenants()
  const { setImpersonate } = useImpersonation()
  const [tenant, setTenant] = useState<AdminTenantDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const loadTenant = useCallback(async () => {
    if (!slug) return
    setTenant(await fetchAdminTenant(await getToken("cognito"), slug))
  }, [slug])

  useEffect(() => {
    if (!slug) {
      setLoading(false)
      return
    }
    void loadTenant().finally(() => setLoading(false))
  }, [slug, loadTenant])

  const handleDelete = async () => {
    if (!slug) return false
    const ok = await deleteAdminTenant(await getToken("cognito"), slug)
    if (ok) navigate("/admin/tenants")
    return ok
  }

  if (superadminLoading) return <Page><LoadingState label="Loading…" /></Page>
  if (!isSuperadmin) return <Navigate to="/" replace />
  if (!slug) return <Navigate to="/admin/tenants" replace />
  if (loading) return <Page><LoadingState label="Loading tenant…" /></Page>
  if (!tenant) {
    return (
      <Page>
        <EmptyState
          icon={Building2}
          title="Tenant not found"
          description={<>No tenant with slug <span className="font-mono">{slug}</span>.</>}
          action={
            <Button asChild variant="outline">
              <Link to="/admin/tenants">Back to tenants</Link>
            </Button>
          }
        />
      </Page>
    )
  }

  const basePath = `/admin/tenants/${slug}`
  const activeTab = siteId ? "sites" : tab

  return (
    <Page>
      <PageHeader
        back={{ to: "/admin/tenants", label: "Tenants" }}
        eyebrow="Tenant"
        title={tenant.name || tenant.slug}
        meta={<TierBadge tier={tenant.tier} />}
        description={<span className="font-mono">{tenant.slug}.echo9.net</span>}
        actions={
          <>
            <Button variant="outline" onClick={() => { setImpersonate(slug); navigate(`/${slug}`) }}>
              <UserCog className="size-4" />
              Impersonate
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon">
                  <MoreHorizontal className="size-4" />
                  <span className="sr-only">More tenant actions</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem variant="destructive" onSelect={() => setDeleteOpen(true)}>
                  <Trash2 className="size-4" />
                  Delete tenant
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        }
      />

      <nav aria-label="Tenant sections" className="-mx-4 overflow-x-auto border-b px-4 sm:mx-0 sm:px-0">
        <div className="flex min-w-max gap-1">
          {TABS.map((t) => {
            const active = activeTab === t.id
            return (
              <Link
                key={t.id}
                to={t.id === "settings" ? basePath : `${basePath}/${t.id}`}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "-mb-px flex items-center gap-2 rounded-t-sm border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:border-border hover:text-foreground"
                )}
              >
                <t.icon className={cn("size-4", active && "text-primary")} aria-hidden />
                {t.label}
              </Link>
            )
          })}
        </div>
      </nav>

      <TenantScopeProvider tenantSlug={slug} basePath={basePath} isSuperadminImpersonating embedded>
        <TenantTierProvider>
          {siteId ? (
            <SiteContentEditor />
          ) : activeTab === "sites" ? (
            <TenantSites />
          ) : activeTab === "domains" ? (
            <TenantDomains />
          ) : activeTab === "users" ? (
            <TenantUsers />
          ) : (
            <AdminSettingsTab tenant={tenant} onSaved={loadTenant} />
          )}
        </TenantTierProvider>
      </TenantScopeProvider>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={`Delete tenant “${slug}”?`}
        description="This permanently deletes the tenant and all its sites, domains, users, and settings. This action cannot be undone."
        confirmLabel="Delete tenant"
        onConfirm={handleDelete}
      />
    </Page>
  )
}

/** Platform-level tenant settings (tier, owner, module overrides) — superadmin only. */
function AdminSettingsTab({
  tenant,
  onSaved,
}: {
  tenant: AdminTenantDetail
  onSaved: () => void
}) {
  const [name, setName] = useState(tenant.name)
  const [tier, setTier] = useState(tenant.tier)
  const [ownerSub, setOwnerSub] = useState<string>(tenant.owner_sub ?? "")
  const [moduleOverrides, setModuleOverrides] = useState<Record<string, boolean>>(
    tenant.module_overrides ?? DEFAULT_MODULE_OVERRIDES
  )
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    setName(tenant.name)
    setTier(tenant.tier)
    setOwnerSub(tenant.owner_sub ?? "")
    setModuleOverrides(tenant.module_overrides ?? DEFAULT_MODULE_OVERRIDES)
  }, [tenant.slug, tenant.name, tenant.tier, tenant.owner_sub, tenant.module_overrides])

  const { users } = useTenantUsers()
  const cognitoUsers = users
    .filter((u) => u.type !== "tuser")
    .map((u) => ({ sub: u.sub, email: u.email ?? "", name: u.name ?? u.email ?? u.sub }))

  const handleSave = async () => {
    setSaveError(null)
    setSaving(true)
    const result = await putAdminTenantSettings(await getToken("cognito"), tenant.slug, {
      name,
      tier,
      module_overrides: moduleOverrides,
      owner_sub: ownerSub || undefined,
    })
    setSaving(false)
    if (result) {
      void onSaved()
    } else {
      setSaveError("Failed to save settings. Please try again.")
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Platform settings</CardTitle>
        <CardDescription>Name, tier, owner and module overrides. Only superadmins can change these.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField label="Name" htmlFor="admin-tenant-name">
            <Input id="admin-tenant-name" value={name} onChange={(e) => setName(e.target.value)} />
          </FormField>
          <FormField label="Tier" htmlFor="admin-tenant-tier">
            <NativeSelect id="admin-tenant-tier" value={tier} onChange={(e) => setTier(e.target.value)}>
              <option value="FREE">Free</option>
              <option value="PRO">Pro</option>
              <option value="BUSINESS">Business</option>
              <option value="VIP">VIP</option>
            </NativeSelect>
          </FormField>
        </div>
        <FormField
          label="Owner"
          htmlFor="admin-tenant-owner"
          hint="Accounts only. Site users (TUSER) cannot own a tenant."
        >
          <NativeSelect id="admin-tenant-owner" value={ownerSub} onChange={(e) => setOwnerSub(e.target.value)}>
            <option value="">— No owner —</option>
            {cognitoUsers.map((u) => (
              <option key={u.sub} value={u.sub}>
                {u.email || u.name || u.sub}
              </option>
            ))}
          </NativeSelect>
        </FormField>
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Module overrides</legend>
          <p className="text-xs text-muted-foreground">Force a module on for this tenant regardless of its tier.</p>
          <div className="grid gap-px overflow-hidden rounded-md border bg-border sm:grid-cols-2">
            {ALL_MODULE_KEYS.map((key) => (
              <label
                key={key}
                className="flex cursor-pointer items-center justify-between gap-3 bg-card px-3 py-2.5 hover:bg-accent"
              >
                <span className="text-sm capitalize">{key.replace("_", " ")}</span>
                <Switch
                  checked={moduleOverrides[key] ?? false}
                  onCheckedChange={(v) => setModuleOverrides((m) => ({ ...m, [key]: v }))}
                  aria-label={key.replace("_", " ")}
                />
              </label>
            ))}
          </div>
        </fieldset>
        {saveError && <Notice tone="danger">{saveError}</Notice>}
        <div className="flex justify-end border-t pt-4">
          <Button onClick={handleSave} disabled={saving}>{saving ? "Saving…" : "Save changes"}</Button>
        </div>
      </CardContent>
    </Card>
  )
}

export { AdministerTenantPage }
