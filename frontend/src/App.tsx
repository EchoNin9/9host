import { Link, Navigate, Route, BrowserRouter, Routes, useLocation } from "react-router-dom"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { TenantAdminLayout } from "@/components/tenant-admin-layout"
import { TenantDashboard } from "@/pages/tenant-dashboard"
import { TenantAnalytics } from "@/pages/tenant-analytics"
import { TenantSites } from "@/pages/tenant-sites"
import { TenantDomains } from "@/pages/tenant-domains"
import { TenantSettings } from "@/pages/tenant-settings"
import { TenantUsers } from "@/pages/tenant-users"
import { SuperadminPage } from "@/pages/superadmin"
import { AdminTemplatesPage } from "@/pages/admin-templates"
import { Login } from "@/pages/login"
import { Signup } from "@/pages/signup"
import { AuthConfirm } from "@/pages/auth-confirm"
import { useTenant } from "@/hooks/use-tenant"
import { useEffect } from "react"

/** Syncs tenant context when URL changes (fixes nav/links not working after navigation) */
function TenantLocationSync() {
  const location = useLocation()
  const { refresh } = useTenant()
  useEffect(() => {
    refresh()
  }, [location.pathname, location.key, refresh])
  return null
}
import { useTenants } from "@/hooks/use-tenants"
import { useAuth } from "@/hooks/use-auth"

function Landing() {
  const { tenants, loading } = useTenants()
  const { isAuthenticated, loading: authLoading } = useAuth()
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
              <Button asChild variant="link" className="p-0">
                <Link to="/admin">Platform admin</Link>
              </Button>
            )}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

/** Redirects / to /:tenant when on subdomain so we use consistent path-based routes */
function TenantRootRedirect() {
  const { tenantSlug } = useTenant()
  if (!tenantSlug) return null
  return <Navigate to={`/${tenantSlug}`} replace />
}

function AppRoutes() {
  const { hasTenant } = useTenant()

  if (!hasTenant) {
    return (
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/admin" element={<SuperadminPage />} />
        <Route path="/admin/templates" element={<AdminTemplatesPage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/auth/confirm" element={<AuthConfirm />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route path="/" element={<TenantRootRedirect />} />
      <Route path="/:tenantSlug" element={<TenantAdminLayout />}>
        <Route index element={<TenantDashboard />} />
        <Route path="analytics" element={<TenantAnalytics />} />
        <Route path="sites" element={<TenantSites />} />
        <Route path="domains" element={<TenantDomains />} />
        <Route path="users" element={<TenantUsers />} />
        <Route path="settings" element={<TenantSettings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <TenantLocationSync />
      <AppRoutes />
    </BrowserRouter>
  )
}

export default App
