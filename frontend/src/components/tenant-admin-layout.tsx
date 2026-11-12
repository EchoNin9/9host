"use client"

import { Outlet, useLocation } from "react-router-dom"

import { TenantTierProvider } from "@/contexts/tenant-tier-provider"
import { TenantAdminSidebar } from "@/components/tenant-admin-sidebar"
import { ImpersonationBanner, ShellHeader, type Crumb } from "@/components/app-shell"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantScope } from "@/context/tenant-scope-context"
import { useImpersonation } from "@/hooks/use-impersonation"

const SECTION_LABELS: Record<string, string> = {
  sites: "Sites",
  domains: "Domains",
  analytics: "Analytics",
  users: "Users & roles",
  modules: "Modules",
  settings: "Settings",
}

function useTenantCrumbs(): Crumb[] {
  const { tenantSlug, tenantBasePath } = useTenant()
  const { pathname } = useLocation()
  const base = tenantBasePath || `/${tenantSlug}`
  const rest = pathname.startsWith(base) ? pathname.slice(base.length) : pathname
  const parts = rest.split("/").filter(Boolean)
  const crumbs: Crumb[] = [{ label: <span className="font-mono">{tenantSlug}</span>, to: base }]
  if (parts.length === 0) {
    crumbs.push({ label: "Overview" })
    return crumbs
  }
  const section = SECTION_LABELS[parts[0]]
  if (section) crumbs.push({ label: section, to: `${base}/${parts[0]}` })
  if (parts[0] === "sites" && parts[2] === "edit") crumbs.push({ label: "Content editor" })
  return crumbs
}

function TenantShellHeader() {
  return <ShellHeader crumbs={useTenantCrumbs()} />
}

function TenantImpersonationBanner() {
  const { isSuperadminImpersonating, tenantSlug } = useTenantScope()
  const { clearImpersonate } = useImpersonation()
  if (!isSuperadminImpersonating || !tenantSlug) return null
  return <ImpersonationBanner tenantSlug={tenantSlug} onStop={clearImpersonate} />
}

function TenantAdminLayout() {
  return (
    <TenantTierProvider>
      <SidebarProvider>
        <TenantAdminSidebar />
        <SidebarInset>
          <TenantShellHeader />
          <TenantImpersonationBanner />
          <Outlet />
        </SidebarInset>
      </SidebarProvider>
    </TenantTierProvider>
  )
}

export { TenantAdminLayout }
