import { Link, Navigate, Route, BrowserRouter, Routes } from "react-router-dom"
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
import { TenantSites } from "@/pages/tenant-sites"
import { TenantDomains } from "@/pages/tenant-domains"
import { TenantSettings } from "@/pages/tenant-settings"
import { useTenant } from "@/hooks/use-tenant"
import { getDemoTenants } from "@/lib/tenant-list"

function Landing() {
  const tenants = getDemoTenants()
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
            {tenants.map((slug) => (
              <Button key={slug} asChild variant="secondary">
                <Link to={`/${slug}`}>{slug}</Link>
              </Button>
            ))}
          </div>
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route path="/" element={<TenantRootRedirect />} />
      <Route path="/:tenantSlug" element={<TenantAdminLayout />}>
        <Route index element={<TenantDashboard />} />
        <Route path="sites" element={<TenantSites />} />
        <Route path="domains" element={<TenantDomains />} />
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
