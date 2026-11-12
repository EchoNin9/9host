"use client"

import { Link, useNavigate } from "react-router-dom"
import { signOut } from "aws-amplify/auth"
import { Building2, LayoutDashboard, LayoutGrid, Layers, RadioTower, UserRound } from "lucide-react"

import { useAuth } from "@/hooks/use-auth"
import { BrandMark, NavGroup, UserMenu, type NavItem } from "@/components/app-shell"
import { Badge } from "@/components/ui/badge"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"

function SuperadminSidebar() {
  const navigate = useNavigate()
  const { userDisplay } = useAuth()

  const overviewNav: NavItem[] = [{ title: "Dashboard", href: "/admin", icon: LayoutDashboard, exact: true }]
  const platformNav: NavItem[] = [
    { title: "Tenants", href: "/admin/tenants", icon: Building2 },
    { title: "Users", href: "/admin/users", icon: UserRound },
    { title: "Templates", href: "/admin/templates", icon: Layers },
    { title: "Edge & domains", href: "/admin/edge", icon: RadioTower },
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
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <Link
              to="/admin"
              className="flex items-center gap-2 rounded-md p-2 group-data-[collapsible=icon]:p-0"
            >
              <BrandMark />
              <span className="grid min-w-0 flex-1 leading-tight group-data-[collapsible=icon]:hidden">
                <span className="truncate text-sm font-semibold">Echo9</span>
                <span className="truncate font-mono text-[0.6875rem] text-muted-foreground">platform console</span>
              </span>
              <Badge tone="brand" mono className="group-data-[collapsible=icon]:hidden">
                Root
              </Badge>
            </Link>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <NavGroup label="Overview" items={overviewNav} />
        <NavGroup label="Platform" items={platformNav} />
      </SidebarContent>

      <SidebarFooter>
        <UserMenu userDisplay={userDisplay} subtitle="Superadmin" onSignOut={handleSignOut}>
          <DropdownMenuItem asChild>
            <Link to="/?choose=1">
              <LayoutGrid className="size-4" />
              My tenants
            </Link>
          </DropdownMenuItem>
        </UserMenu>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}

export { SuperadminSidebar }
