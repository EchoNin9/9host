import { useState, useCallback, useEffect } from "react"
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
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
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
import { ArrowLeft, Globe, GlobeLock, Settings, Trash2, Users } from "lucide-react"

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
  const [deleting, setDeleting] = useState(false)

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
    if (!slug) return
    setDeleting(true)
    const ok = await deleteAdminTenant(await getToken("cognito"), slug)
    setDeleting(false)
    if (ok) {
      setDeleteOpen(false)
      navigate("/admin/tenants")
    }
  }

  if (superadminLoading) return <div className="flex min-h-screen items-center justify-center">Loading…</div>
  if (!isSuperadmin) return <Navigate to="/" replace />
  if (!slug) return <Navigate to="/admin/tenants" replace />
  if (loading) return <div className="flex min-h-screen items-center justify-center">Loading…</div>
  if (!tenant) return <div className="p-6">Tenant not found.</div>

  const basePath = `/admin/tenants/${slug}`
  const activeTab = siteId ? "sites" : tab

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/admin/tenants"
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back to tenants
          </Link>
          <div>
            <h1 className="text-2xl font-semibold">{tenant.name || tenant.slug}</h1>
            <p className="text-muted-foreground">
              {tenant.slug} · {tenant.tier}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => { setImpersonate(slug); navigate(`/${slug}`) }}>
            Impersonate
          </Button>
          <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="mr-2 size-4" />
            Delete tenant
          </Button>
        </div>
      </div>

      <nav aria-label="Tenant sections" className="flex gap-2 border-b">
        {TABS.map((t) => (
          <Link
            key={t.id}
            to={t.id === "settings" ? basePath : `${basePath}/${t.id}`}
            aria-current={activeTab === t.id ? "page" : undefined}
            className={`flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === t.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <t.icon className="size-4" />
            {t.label}
          </Link>
        ))}
      </nav>

      <TenantScopeProvider tenantSlug={slug} basePath={basePath} isSuperadminImpersonating>
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

      <AlertDialog open={deleteOpen} onOpenChange={(o) => !o && !deleting && setDeleteOpen(false)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete tenant &quot;{slug}&quot;?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the tenant and all its sites, domains, users, and settings. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? "Deleting…" : "Delete tenant"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
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
        <CardTitle>Settings</CardTitle>
        <CardDescription>Update tenant configuration</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label htmlFor="admin-tenant-name" className="text-sm font-medium">Name</label>
          <Input id="admin-tenant-name" value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
        </div>
        <div>
          <label htmlFor="admin-tenant-tier" className="text-sm font-medium">Tier</label>
          <select
            id="admin-tenant-tier"
            value={tier}
            onChange={(e) => setTier(e.target.value)}
            className="mt-1 flex h-9 w-full rounded-md border border-input px-3 py-1 text-sm"
          >
            <option value="FREE">Free</option>
            <option value="PRO">Pro</option>
            <option value="BUSINESS">Business</option>
            <option value="VIP">VIP</option>
          </select>
        </div>
        <div>
          <label htmlFor="admin-tenant-owner" className="text-sm font-medium">Owner</label>
          <p className="text-xs text-muted-foreground mt-1 mb-2">
            Cognito users only. DB users (TUSER) cannot be owner.
          </p>
          <select
            id="admin-tenant-owner"
            value={ownerSub}
            onChange={(e) => setOwnerSub(e.target.value)}
            className="mt-1 flex h-9 w-full rounded-md border border-input px-3 py-1 text-sm"
          >
            <option value="">— No owner —</option>
            {cognitoUsers.map((u) => (
              <option key={u.sub} value={u.sub}>
                {u.email || u.name || u.sub}
              </option>
            ))}
          </select>
        </div>
        <fieldset>
          <legend className="text-sm font-medium">Module overrides</legend>
          <div className="mt-2 space-y-2">
            {ALL_MODULE_KEYS.map((key) => (
              <label key={key} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={moduleOverrides[key] ?? false}
                  onChange={(e) => setModuleOverrides((m) => ({ ...m, [key]: e.target.checked }))}
                  className="h-4 w-4"
                />
                <span className="text-sm capitalize">{key.replace("_", " ")}</span>
              </label>
            ))}
          </div>
        </fieldset>
        {saveError && (
          <p className="text-sm text-destructive">{saveError}</p>
        )}
        <Button onClick={handleSave} disabled={saving}>{saving ? "Saving…" : "Save"}</Button>
      </CardContent>
    </Card>
  )
}

export { AdministerTenantPage }
