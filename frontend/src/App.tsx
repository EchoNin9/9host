import { Link, Navigate, Outlet, Route, BrowserRouter, Routes, useParams } from "react-router-dom"
import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Input } from "@/components/ui/input"
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
import { Login } from "@/pages/login"
import { SiteLogin } from "@/pages/site-login"
import { Signup } from "@/pages/signup"
import { AuthConfirm } from "@/pages/auth-confirm"
import { useTenants } from "@/hooks/use-tenants"
import { useAuth } from "@/hooks/use-auth"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import {
  TenantContext,
  extractTenantFromHost,
  getSwitchTenantUrl,
  type TenantContextValue,
} from "@/contexts/tenant-context"
import { createTenantWithError, fetchDefaultSite, getToken } from "@/lib/api"

/**
 * Provides tenant context derived from React Router's :tenantSlug param.
 * Overrides the parent TenantProvider so all tenant-scoped components
 * get the slug synchronously from the router instead of from window.location.
 */
function TenantRouteProvider() {
  const { tenantSlug: routeSlug } = useParams<{ tenantSlug: string }>()
  const slug = routeSlug ?? null
  const basePath = slug ? `/${slug}` : ""

  const getSwitchUrl = useCallback(
    (newSlug: string) => getSwitchTenantUrl(newSlug, basePath),
    [basePath]
  )

  const value = useMemo<TenantContextValue>(
    () => ({
      tenantSlug: slug,
      hasTenant: slug !== null,
      tenantBasePath: basePath,
      refresh: () => {},
      getSwitchTenantUrl: getSwitchUrl,
    }),
    [slug, basePath, getSwitchUrl]
  )

  return (
    <TenantContext.Provider value={value}>
      <TenantAdminLayout />
    </TenantContext.Provider>
  )
}

/**
 * Root route: redirects to default site or /:tenantSlug when accessed via tenant subdomain,
 * otherwise renders the Landing page (Task 1.98).
 */
function RootRoute() {
  const subdomainSlug = useMemo(
    () => extractTenantFromHost(window.location.hostname),
    []
  )
  const [resolving, setResolving] = useState(true)
  const [redirectTo, setRedirectTo] = useState<string | null>(null)

  useEffect(() => {
    if (!subdomainSlug) {
      setResolving(false)
      return
    }
    let cancelled = false
    fetchDefaultSite(subdomainSlug).then((data) => {
      if (cancelled) return
      if (data?.site_id) {
        const tenant = data.tenant_slug ?? subdomainSlug
        setRedirectTo(`/site/${tenant}/${data.site_id}/`)
      } else {
        setRedirectTo(`/${subdomainSlug}`)
      }
      setResolving(false)
    }).catch(() => {
      if (!cancelled) {
        setRedirectTo(`/${subdomainSlug}`)
        setResolving(false)
      }
    })
    return () => { cancelled = true }
  }, [subdomainSlug])

  if (!subdomainSlug) return <Landing />
  if (resolving) return null
  if (redirectTo) return <Navigate to={redirectTo} replace />
  return <Navigate to={`/${subdomainSlug}`} replace />
}

function CreateTenantSheet({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: () => void
}) {
  const [slug, setSlug] = useState("")
  const [name, setName] = useState("")
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
    const result = await createTenantWithError(token, {
      slug: s,
      name: name.trim() || undefined,
    })
    setSaving(false)
    if (result.ok) {
      onCreated()
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
          <SheetTitle>Create your tenant</SheetTitle>
        </SheetHeader>
        <div className="mt-6 space-y-4">
          <div>
            <label className="text-sm font-medium">Slug</label>
            <Input
              value={slug}
              onChange={handleSlugChange}
              placeholder="acme-corp"
              maxLength={60}
              className="mt-1"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Lowercase letters, numbers, hyphens. Max 60 chars. Used in URL (e.g. acme.echo9.net).
            </p>
          </div>
          <div>
            <label className="text-sm font-medium">Display name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Acme Corp"
              className="mt-1"
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button onClick={handleCreate} disabled={saving} className="w-full">
            {saving ? "Creating…" : "Create tenant"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}

function Landing() {
  const { tenants, loading, refetch } = useTenants()
  const { isAuthenticated, loading: authLoading } = useAuth()
  const { isSuperadmin, loading: superadminLoading } = useAdminTenants()
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)

  useEffect(() => {
    if (!authLoading && isAuthenticated && !loading && !superadminLoading) {
      if (isSuperadmin) {
        navigate("/admin", { replace: true })
      } else if (tenants.length >= 1) {
        navigate(`/${tenants[0].slug}`, { replace: true })
      }
    }
  }, [authLoading, isAuthenticated, loading, superadminLoading, isSuperadmin, tenants, navigate])

  const handleTenantCreated = useCallback(() => {
    void refetch()
    // Refetch updates tenants; useEffect will navigate to tenants[0] when tenants.length >= 1
  }, [refetch])

  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>9host</CardTitle>
          <CardDescription>
            Multi-tenant website hosting platform
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-sm text-muted-foreground">
            Visit a tenant subdomain (e.g. acme.echo9.net) or path (e.g.
            /acme) to access the admin.
          </p>
          <div className="flex flex-wrap gap-2">
            {loading ? (
              <span className="text-sm text-muted-foreground">Loading…</span>
            ) : tenants.length > 0 ? (
              tenants.map((t) => (
                <Button key={t.slug} asChild variant="secondary">
                  <Link to={`/${t.slug}`}>{t.name || t.slug}</Link>
                </Button>
              ))
            ) : !authLoading && isAuthenticated ? (
              <span className="text-sm text-muted-foreground">
                You have no tenants yet.
              </span>
            ) : (
              <span className="text-sm text-muted-foreground">
                Sign in to see your tenants.
              </span>
            )}
          </div>
          <p className="mt-4 flex flex-wrap justify-center gap-4">
            {!authLoading && !isAuthenticated && (
              <Button asChild variant="link" className="p-0">
                <Link to="/login">Sign in</Link>
              </Button>
            )}
            {!authLoading && isAuthenticated && (
              <>
                <Button
                  variant="link"
                  className="p-0"
                  onClick={() => setCreateOpen(true)}
                >
                  Create tenant
                </Button>
                {isSuperadmin && (
                  <Button asChild variant="link" className="p-0">
                    <Link to="/admin">Platform admin</Link>
                  </Button>
                )}
              </>
            )}
          </p>
        </CardContent>
      </Card>
      {isAuthenticated && (
        <CreateTenantSheet
          open={createOpen}
          onOpenChange={setCreateOpen}
          onCreated={handleTenantCreated}
        />
      )}
    </div>
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
      <Route path="/" element={<RootRoute />} />
      <Route path="/admin" element={<SuperadminLayout />}>
        <Route index element={<SuperadminDashboard />} />
        <Route path="tenants" element={<Outlet />}>
          <Route index element={<SuperadminTenantsPage />} />
          <Route path=":slug" element={<AdministerTenantPage />} />
        </Route>
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="templates" element={<AdminTemplatesPage />} />
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
