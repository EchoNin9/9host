"use client"

import { Link, useNavigate } from "react-router-dom"
import { signOut } from "aws-amplify/auth"
import {
  BarChart3,
  Globe,
  GlobeLock,
  LayoutDashboard,
  LayoutGrid,
  Package,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react"

import { clearSiteToken } from "@/lib/api"
import { useAuth } from "@/hooks/use-auth"
import { useTenant } from "@/hooks/use-tenant"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { TenantSwitcher } from "@/components/tenant-switcher"
import { NavGroup, UserMenu, type NavItem } from "@/components/app-shell"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail } from "@/components/ui/sidebar"

function TenantAdminSidebar() {
  const { tenantSlug, tenantBasePath } = useTenant()
  const { isSuperadmin } = useAdminTenants()
  const { isSiteUser, userDisplay } = useAuth()
  const navigate = useNavigate()
  const base = tenantBasePath || `/${tenantSlug}`

  const handleSignOut = async () => {
    try {
      if (isSiteUser) {
        clearSiteToken()
      } else {
        await signOut()
      }
      navigate("/login")
    } catch (error) {
      console.error("Error signing out: ", error)
    }
  }

  const workspaceNav: NavItem[] = [
    { title: "Overview", href: base, icon: LayoutDashboard, exact: true },
    { title: "Sites", href: `${base}/sites`, icon: Globe },
    { title: "Domains", href: `${base}/domains`, icon: GlobeLock },
    { title: "Analytics", href: `${base}/analytics`, icon: BarChart3 },
  ]
  const manageNav: NavItem[] = [
    { title: "Users & roles", href: `${base}/users`, icon: Users },
    { title: "Modules", href: `${base}/modules`, icon: Package },
    { title: "Settings", href: `${base}/settings`, icon: Settings },
  ]

  return (
    <Sidebar collapsible="icon" variant="inset">
      <SidebarHeader>
        <TenantSwitcher />
      </SidebarHeader>

      <SidebarContent>
        <NavGroup label="Workspace" items={workspaceNav} />
        <NavGroup label="Manage" items={manageNav} />
      </SidebarContent>

      <SidebarFooter>
        <UserMenu
          userDisplay={userDisplay}
          subtitle={isSiteUser ? "Site login" : undefined}
          onSignOut={handleSignOut}
        >
          {isSuperadmin && !isSiteUser && (
            <DropdownMenuItem asChild>
              <Link to="/admin">
                <ShieldCheck className="size-4" />
                Platform admin
              </Link>
            </DropdownMenuItem>
          )}
          {!isSiteUser && (
            <DropdownMenuItem asChild>
              <Link to="/?choose=1">
                <LayoutGrid className="size-4" />
                All tenants
              </Link>
            </DropdownMenuItem>
          )}
        </UserMenu>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}

export { TenantAdminSidebar }
