import { Link, Navigate, Outlet, Route, BrowserRouter, Routes, useParams, useSearchParams } from "react-router-dom"
import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { ArrowRight, Plus, ShieldCheck } from "lucide-react"
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
import { AuthLayout, FullScreenLoading } from "@/components/auth-layout"
import { FormField, LoadingState, Notice } from "@/components/page"
import { TenantAdminLayout } from "@/components/tenant-admin-layout"
import { TenantDashboard } from "@/pages/tenant-dashboard"
import { TenantAnalytics } from "@/pages/tenant-analytics"
import { TenantSites } from "@/pages/tenant-sites"
import { SiteContentEditor } from "@/pages/site-content-editor"
import { TenantDomains } from "@/pages/tenant-domains"
import { TenantSettings } from "@/pages/tenant-settings"
import { TenantModules } from "@/pages/tenant-modules"
import { TenantUsers } from "@/pages/tenant-users"
import { SuperadminLayout } from "@/components/superadmin-layout"
import { SuperadminDashboard } from "@/pages/superadmin-dashboard"
import { SuperadminTenantsPage } from "@/pages/superadmin-tenants"
import { AdministerTenantPage } from "@/pages/administer-tenant"
import { AdminTemplatesPage } from "@/pages/admin-templates"
import { AdminUsersPage } from "@/pages/admin-users"
import { AdminEdgeHealthPage } from "@/pages/admin-edge-health"
import { Login } from "@/pages/login"
import { SiteLogin } from "@/pages/site-login"
import { Signup } from "@/pages/signup"
import { AuthConfirm } from "@/pages/auth-confirm"
import { useTenants } from "@/hooks/use-tenants"
import { useAuth } from "@/hooks/use-auth"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { useImpersonation } from "@/hooks/use-impersonation"
import { TenantScopeProvider } from "@/context/tenant-scope"
import { createTenantWithError, getToken } from "@/lib/api"

/**
 * Tenant dashboard shell (/:tenantSlug/*). Resource views get their API client from
 * TenantScope; impersonation applies only when a superadmin explicitly chose this tenant.
 */
function TenantRouteProvider() {
  const { tenantSlug } = useParams<{ tenantSlug: string }>()
  const { impersonateTenant } = useImpersonation()
  if (!tenantSlug) return <Navigate to="/" replace />
  return (
    <TenantScopeProvider
      tenantSlug={tenantSlug}
      isSuperadminImpersonating={impersonateTenant === tenantSlug}
    >
      <TenantAdminLayout />
    </TenantScopeProvider>
  )
}

function CreateTenantSheet({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (slug: string) => void
}) {
  const [slug, setSlug] = useState("")
  const [name, setName] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSlugChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value.toLowerCase().replace(/\s/g, "-").replace(/[^a-z0-9-]/g, "")
    setSlug(v.slice(0, 60))
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
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
    const result = await createTenantWithError(token, {
      slug: s,
      name: name.trim() || undefined,
    })
    setSaving(false)
    if (result.ok) {
      onCreated(result.data?.slug || s)
      onOpenChange(false)
      setSlug("")
      setName("")
    } else {
      setError(result.error)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent aria-describedby={undefined}>
        <SheetHeader>
          <SheetTitle>Create a tenant</SheetTitle>
          <SheetDescription>A tenant holds your sites, domains and team.</SheetDescription>
        </SheetHeader>
        <form onSubmit={handleCreate} className="flex flex-1 flex-col gap-5">
          <FormField label="Display name" htmlFor="new-tenant-name">
            <Input
              id="new-tenant-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Acme Corp"
            />
          </FormField>
          <FormField
            label="Slug"
            htmlFor="new-tenant-slug"
            hint={
              <>
                Lowercase letters, numbers and hyphens. Your default address is{" "}
                <span className="font-mono text-foreground">{slug || "acme-corp"}.echo9.net</span>
              </>
            }
          >
            <Input
              id="new-tenant-slug"
              value={slug}
              onChange={handleSlugChange}
              placeholder="acme-corp"
              maxLength={60}
              className="font-mono"
              required
            />
          </FormField>
          {error && <Notice tone="danger">{error}</Notice>}
          <SheetFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Creating…" : "Create tenant"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}

function Landing() {
  const { tenants, loading, refetch } = useTenants()
  const { isAuthenticated, loading: authLoading } = useAuth()
  const { isSuperadmin, loading: superadminLoading } = useAdminTenants()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  // ?choose=1 comes from "All tenants" in the shell: show the picker instead of bouncing back.
  const choosing = searchParams.get("choose") === "1"
  const [createOpen, setCreateOpen] = useState(false)

  useEffect(() => {
    if (choosing) return
    if (!authLoading && isAuthenticated && !loading && !superadminLoading) {
      if (isSuperadmin) {
        navigate("/admin", { replace: true })
      } else if (tenants.length >= 1) {
        navigate(`/${tenants[0].slug}`, { replace: true })
      }
    }
  }, [choosing, authLoading, isAuthenticated, loading, superadminLoading, isSuperadmin, tenants, navigate])

  const handleTenantCreated = useCallback(
    (slug: string) => {
      // Refresh the tenant list (role lookups read it), then open the new tenant.
      void refetch().then(() => navigate(`/${slug}`))
    },
    [refetch, navigate]
  )

  if (authLoading) return <FullScreenLoading />
  if (!isAuthenticated) return <Navigate to="/login" replace />

  return (
    <AuthLayout
      title={tenants.length > 0 ? "Choose a tenant" : "Create your first tenant"}
      description={
        tenants.length > 0
          ? "Pick the tenant you want to manage."
          : "A tenant holds your sites, custom domains and team. You can add more later."
      }
    >
      {loading ? (
        <LoadingState rows={2} label="Loading tenants…" />
      ) : tenants.length > 0 ? (
        <ul className="-mx-2 space-y-1">
          {tenants.map((t) => (
            <li key={t.slug}>
              <Link
                to={`/${t.slug}`}
                className="group flex items-center gap-3 rounded-md px-2 py-2.5 hover:bg-accent"
              >
                <span
                  aria-hidden
                  className="flex size-8 shrink-0 items-center justify-center rounded-md border bg-muted font-mono text-xs font-semibold uppercase"
                >
                  {(t.name || t.slug).slice(0, 2)}
                </span>
                <span className="grid min-w-0 flex-1 leading-tight">
                  <span className="truncate font-medium">{t.name || t.slug}</span>
                  <span className="truncate font-mono text-xs text-muted-foreground">
                    {t.slug} · {t.role}
                  </span>
                </span>
                <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="mt-5 flex flex-col gap-2 border-t pt-5">
        <Button variant={tenants.length > 0 ? "outline" : "default"} onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" />
          Create tenant
        </Button>
        {isSuperadmin && (
          <Button asChild variant="ghost">
            <Link to="/admin">
              <ShieldCheck className="size-4" />
              Platform admin
            </Link>
          </Button>
        )}
      </div>
      <CreateTenantSheet
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={handleTenantCreated}
      />
    </AuthLayout>
  )
}

/**
 * Single merged route tree. React Router v6 matches static routes
 * (/admin, /login, etc.) before dynamic segments (/:tenantSlug),
 * so no conditional hasTenant branching is needed.
 */
function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/admin" element={<SuperadminLayout />}>
        <Route index element={<SuperadminDashboard />} />
        <Route path="tenants" element={<Outlet />}>
          <Route index element={<SuperadminTenantsPage />} />
          <Route path=":slug" element={<AdministerTenantPage />} />
          <Route path=":slug/:tab" element={<AdministerTenantPage />} />
          <Route path=":slug/sites/:siteId/edit" element={<AdministerTenantPage />} />
        </Route>
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="templates" element={<AdminTemplatesPage />} />
        <Route path="edge" element={<AdminEdgeHealthPage />} />
      </Route>
      <Route path="/login/site" element={<SiteLogin />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/auth/confirm" element={<AuthConfirm />} />
      <Route path="/:tenantSlug" element={<TenantRouteProvider />}>
        <Route index element={<TenantDashboard />} />
        <Route path="analytics" element={<TenantAnalytics />} />
        <Route path="sites" element={<TenantSites />} />
        <Route path="sites/:siteId/edit" element={<SiteContentEditor />} />
        <Route path="domains" element={<TenantDomains />} />
        <Route path="users" element={<TenantUsers />} />
        <Route path="modules" element={<TenantModules />} />
        <Route path="settings" element={<TenantSettings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}

export default App
