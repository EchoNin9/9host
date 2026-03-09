"use client"

import { Outlet } from "react-router-dom"

import { TenantAdminSidebar } from "@/components/tenant-admin-sidebar"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"

function TenantAdminLayout() {
  return (
    <SidebarProvider>
      <TenantAdminSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="h-6" />
        </header>
        <Outlet />
      </SidebarInset>
    </SidebarProvider>
  )
}

export { TenantAdminLayout }
