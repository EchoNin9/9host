"use client"

import { Check, ChevronsUpDown, LayoutGrid } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"

import { useTenant } from "@/hooks/use-tenant"
import { useTenants } from "@/hooks/use-tenants"
import { useAuth } from "@/hooks/use-auth"
import { useTier } from "@/hooks/use-tier"
import { BrandMark } from "@/components/app-shell"
import { TierBadge } from "@/components/status-badges"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar"

function SwitcherLabel({ name, slug }: { name: string; slug: string }) {
  const tier = useTier()
  return (
    <>
      <BrandMark />
      <span className="grid min-w-0 flex-1 text-left leading-tight">
        <span className="truncate text-sm font-semibold text-sidebar-foreground">{name}</span>
        <span className="truncate font-mono text-[0.6875rem] text-muted-foreground">{slug}</span>
      </span>
      <TierBadge tier={tier} className="group-data-[collapsible=icon]:hidden" />
    </>
  )
}

/** Sidebar header: current tenant (name, slug, tier) with a menu to switch tenants. */
function TenantSwitcher() {
  const { tenantSlug, getSwitchTenantUrl } = useTenant()
  const { tenants, loading } = useTenants()
  const { isSiteUser } = useAuth()
  const navigate = useNavigate()

  if (!tenantSlug) return null
  const current = tenants.find((t) => t.slug === tenantSlug)
  const name = current?.name || tenantSlug

  if (isSiteUser) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <div className="flex items-center gap-2 p-2 group-data-[collapsible=icon]:p-0">
            <SwitcherLabel name={name} slug={tenantSlug} />
          </div>
        </SidebarMenuItem>
      </SidebarMenu>
    )
  }

  const handleSwitch = (newSlug: string) => {
    const url = getSwitchTenantUrl(newSlug)
    if (url.startsWith("http")) {
      window.location.assign(url)
    } else {
      navigate(url)
    }
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              aria-label={`Current tenant ${name}. Switch tenant`}
              className="data-[state=open]:bg-sidebar-accent group-data-[collapsible=icon]:p-0!"
            >
              <SwitcherLabel name={name} slug={tenantSlug} />
              <ChevronsUpDown className="size-4 text-muted-foreground" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-(--radix-dropdown-menu-trigger-width) min-w-60">
            <DropdownMenuLabel className="eyebrow py-1">Tenants</DropdownMenuLabel>
            {loading ? (
              <DropdownMenuItem disabled>Loading…</DropdownMenuItem>
            ) : (
              tenants.map((t) => (
                <DropdownMenuItem key={t.slug} onSelect={() => handleSwitch(t.slug)}>
                  <span className="grid min-w-0 flex-1 leading-tight">
                    <span className="truncate">{t.name || t.slug}</span>
                    <span className="truncate font-mono text-[0.6875rem] text-muted-foreground">{t.slug}</span>
                  </span>
                  {t.slug === tenantSlug && <Check className="size-4 text-primary" aria-label="Current" />}
                </DropdownMenuItem>
              ))
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link to="/?choose=1">
                <LayoutGrid className="size-4" />
                All tenants
              </Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

export { TenantSwitcher }
