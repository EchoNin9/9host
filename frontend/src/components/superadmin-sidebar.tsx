"use client"

import { Link, useLocation, useNavigate } from "react-router-dom"
import { signOut } from "aws-amplify/auth"
import {
  LayoutDashboard,
  Users,
  UserRound,
  Layers,
  LogOut,
  type LucideIcon,
} from "lucide-react"

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

function SuperadminSidebar() {
  const location = useLocation()
  const navigate = useNavigate()

  const mainNav: NavItem[] = [
    { title: "Dashboard", href: "/admin", icon: LayoutDashboard },
    { title: "Tenants", href: "/admin/tenants", icon: Users },
    { title: "Users", href: "/admin/users", icon: UserRound },
    { title: "Templates", href: "/admin/templates", icon: Layers },
  ]

  const handleSignOut = async () => {
    try {
      await signOut()
      navigate("/login")
    } catch (error) {
      console.error("Error signing out: ", error)
    }
  }

  return (
    <Sidebar collapsible="icon" variant="inset">
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-2 px-4 py-3 font-semibold">
          9host Admin
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Platform</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {mainNav.map((item) => {
                const isActive =
                  location.pathname === item.href ||
                  (item.href !== "/admin" &&
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
        <div className="flex flex-col gap-1">
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

export { SuperadminSidebar }
