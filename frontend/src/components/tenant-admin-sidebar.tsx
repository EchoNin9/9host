"use client"

import { Link, useLocation, useNavigate } from "react-router-dom"
import { signOut } from "aws-amplify/auth"
import {
  LayoutDashboard,
  BarChart3,
  Globe,
  GlobeLock,
  Settings,
  Users,
  UserCog,
  LogOut,
  type LucideIcon,
} from "lucide-react"

import { useTenant } from "@/hooks/use-tenant"
import { useImpersonation } from "@/hooks/use-impersonation"
import { TenantSwitcher } from "@/components/tenant-switcher"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"

interface NavItem {
  title: string
  href: string
  icon: LucideIcon
}

function TenantAdminSidebar() {
  const { tenantSlug, tenantBasePath } = useTenant()
  const { impersonateTenant, clearImpersonate, isImpersonating } =
    useImpersonation()
  const location = useLocation()
  const navigate = useNavigate()
  const base = tenantBasePath || `/${tenantSlug}`

  const handleSignOut = async () => {
    try {
      await signOut()
      navigate("/login")
    } catch (error) {
      console.error("Error signing out: ", error)
    }
  }

  const mainNav: NavItem[] = [
    { title: "Dashboard", href: `${base}`, icon: LayoutDashboard },
    { title: "Analytics", href: `${base}/analytics`, icon: BarChart3 },
    { title: "Sites", href: `${base}/sites`, icon: Globe },
    { title: "Domains", href: `${base}/domains`, icon: GlobeLock },
    { title: "Users", href: `${base}/users`, icon: Users },
    { title: "Settings", href: `${base}/settings`, icon: Settings },
  ]

  return (
    <Sidebar collapsible="icon" variant="inset">
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-2 px-2 py-2">
          <TenantSwitcher />
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Admin</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {mainNav.map((item) => {
                const isActive =
                  location.pathname === item.href ||
                  (item.href !== base &&
                    location.pathname.startsWith(item.href))
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton asChild isActive={isActive}>
                      <Link to={item.href}>
                        <item.icon />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <Separator className="mx-2" />

      <SidebarFooter className="border-t border-sidebar-border p-2 space-y-2">
        {isImpersonating && impersonateTenant && (
          <div className="flex items-center gap-2 rounded-md bg-amber-500/10 px-2 py-1.5 text-xs text-amber-600 dark:text-amber-400">
            <UserCog className="size-3.5 shrink-0" />
            <span>Impersonating {impersonateTenant}</span>
            <Link
              to="/"
              onClick={clearImpersonate}
              className="ml-auto flex items-center gap-1 font-medium hover:underline"
            >
              <LogOut className="size-3" />
              Stop
            </Link>
          </div>
        )}
        <div className="flex flex-col gap-1">
          <Link
            to="/admin"
            className="flex items-center gap-2 text-xs text-sidebar-foreground/70 hover:text-sidebar-foreground"
          >
            <UserCog className="size-3.5" />
            Platform admin
          </Link>
          <Link
            to="/"
            className="text-xs text-sidebar-foreground/70 hover:text-sidebar-foreground"
          >
            ← Back to platform
          </Link>
          <button
            onClick={handleSignOut}
            className="flex items-center gap-2 mt-2 text-xs text-sidebar-foreground/70 hover:text-sidebar-foreground text-left"
          >
            <LogOut className="size-3.5" />
            Sign Out
          </button>
        </div>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}

export { TenantAdminSidebar }
