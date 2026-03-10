"use client"

import { ChevronsUpDown } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { useTenant } from "@/hooks/use-tenant"
import { useTenants } from "@/hooks/use-tenants"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

function TenantSwitcher() {
  const { tenantSlug, getSwitchTenantUrl } = useTenant()
  const { tenants, loading } = useTenants()
  const navigate = useNavigate()

  if (!tenantSlug) return null

  const handleSwitch = (newSlug: string) => {
    const url = getSwitchTenantUrl(newSlug)
    if (url.startsWith("http")) {
      window.location.assign(url)
    } else {
      navigate(url)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="flex h-auto items-center gap-2 px-2 py-2 font-semibold text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          <span>{tenantSlug}</span>
          <ChevronsUpDown className="size-4 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[--radix-dropdown-menu-trigger-width]">
        {loading ? (
          <DropdownMenuItem disabled>Loading…</DropdownMenuItem>
        ) : (
          tenants.map((t) => (
            <DropdownMenuItem
              key={t.slug}
              onClick={() => handleSwitch(t.slug)}
              className={t.slug === tenantSlug ? "bg-accent" : undefined}
            >
              {t.name || t.slug}
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export { TenantSwitcher }
