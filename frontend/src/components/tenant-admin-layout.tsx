"use client"

import { Outlet } from "react-router-dom"

import { TenantTierProvider } from "@/contexts/tenant-tier-provider"
import { TenantAdminSidebar } from "@/components/tenant-admin-sidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"

function TenantAdminLayout() {
  return (
    <TenantTierProvider>
      <SidebarProvider>
        <TenantAdminSidebar />
        <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="h-6" />
          <span className="text-sm font-semibold text-primary">Echo9</span>
        </header>
        <Outlet />
      </SidebarInset>
    </SidebarProvider>
    </TenantTierProvider>
  )
}

export { TenantAdminLayout }
