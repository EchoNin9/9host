"use client"

import { Link, Navigate, Outlet, useLocation } from "react-router-dom"
import { ShieldAlert } from "lucide-react"

import { useAuth } from "@/hooks/use-auth"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { SuperadminSidebar } from "@/components/superadmin-sidebar"
import { ShellHeader, type Crumb } from "@/components/app-shell"
import { AuthLayout, FullScreenLoading } from "@/components/auth-layout"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"

const SECTION_LABELS: Record<string, string> = {
  tenants: "Tenants",
  users: "Users",
  templates: "Templates",
  edge: "Edge & domains",
}

function useAdminCrumbs(): Crumb[] {
  const parts = useLocation().pathname.split("/").filter(Boolean).slice(1)
  const crumbs: Crumb[] = [{ label: "Platform", to: "/admin" }]
  if (parts.length === 0) return [...crumbs, { label: "Dashboard" }]
  const section = SECTION_LABELS[parts[0]]
  if (section) crumbs.push({ label: section, to: `/admin/${parts[0]}` })
  if (parts[0] === "tenants" && parts[1]) {
    crumbs.push({ label: <span className="font-mono">{parts[1]}</span>, to: `/admin/tenants/${parts[1]}` })
  }
  return crumbs
}

function SuperadminLayout() {
  const { isAuthenticated, loading: authLoading } = useAuth()
  const { loading, isSuperadmin } = useAdminTenants()
  const crumbs = useAdminCrumbs()

  if (authLoading || loading) return <FullScreenLoading />

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (!isSuperadmin) {
    return (
      <AuthLayout
        icon={ShieldAlert}
        title="Access denied"
        description="Superadmin access required. You do not have permission to view this page."
      >
        <Button asChild variant="outline" className="w-full">
          <Link to="/">Back to your tenants</Link>
        </Button>
      </AuthLayout>
    )
  }

  return (
    <SidebarProvider>
      <SuperadminSidebar />
      <SidebarInset>
        <ShellHeader crumbs={crumbs} />
        <Outlet />
      </SidebarInset>
    </SidebarProvider>
  )
}

export { SuperadminLayout }
