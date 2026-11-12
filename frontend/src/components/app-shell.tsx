/**
 * Shared app-shell pieces for the Tenant Dashboard and the Superadmin Console (T-30):
 * brand mark, top bar with breadcrumbs, sidebar nav groups, user menu, impersonation banner.
 */

import { Fragment, type ReactNode } from "react"
import { Link, useLocation } from "react-router-dom"
import { ChevronsUpDown, LogOut, Monitor, Moon, Sun, UserCog, type LucideIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Separator } from "@/components/ui/separator"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { useSidebar } from "@/hooks/use-sidebar"
import { useTheme } from "@/hooks/use-theme"
import { cn } from "@/lib/utils"

export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "relative flex size-8 shrink-0 items-center justify-center rounded-md bg-[#181a20] font-mono text-[0.8125rem] font-semibold text-[#f6f5f2] ring-1 ring-black/5 dark:ring-white/10",
        className
      )}
    >
      e9
      <span className="absolute top-1 right-1 size-1.5 rounded-[2px] bg-brand" />
    </span>
  )
}

export interface Crumb {
  label: ReactNode
  to?: string
}

/** Sticky top bar inside the content inset: sidebar toggle + breadcrumb trail. */
export function ShellHeader({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/85 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/70 md:rounded-t-lg">
      <SidebarTrigger className="-ml-1.5" aria-label="Toggle navigation" />
      <Separator orientation="vertical" className="mr-1 h-5" />
      <nav aria-label="Breadcrumb" className="min-w-0">
        <ol className="flex min-w-0 items-center gap-1.5 text-sm">
          {crumbs.map((c, i) => {
            const last = i === crumbs.length - 1
            return (
              <Fragment key={i}>
                {i > 0 && (
                  <li aria-hidden className="hidden text-muted-foreground/60 sm:block">
                    /
                  </li>
                )}
                <li className={cn("min-w-0 truncate", last ? "font-medium text-foreground" : "hidden text-muted-foreground sm:block")}>
                  {c.to && !last ? (
                    <Link to={c.to} className="rounded-sm hover:text-foreground">
                      {c.label}
                    </Link>
                  ) : (
                    <span aria-current={last ? "page" : undefined}>{c.label}</span>
                  )}
                </li>
              </Fragment>
            )
          })}
        </ol>
      </nav>
    </header>
  )
}

export interface NavItem {
  title: string
  href: string
  icon: LucideIcon
  /** Match only the exact path (for index routes like the dashboard). */
  exact?: boolean
}

export function NavGroup({ label, items }: { label: string; items: NavItem[] }) {
  const location = useLocation()
  const { isMobile, setOpenMobile } = useSidebar()
  return (
    <SidebarGroup>
      <SidebarGroupLabel className="eyebrow">{label}</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {items.map((item) => {
            const isActive = item.exact
              ? location.pathname === item.href || location.pathname === `${item.href}/`
              : location.pathname === item.href || location.pathname.startsWith(`${item.href}/`)
            return (
              <SidebarMenuItem key={item.href}>
                <SidebarMenuButton asChild isActive={isActive} tooltip={item.title}>
                  <Link
                    to={item.href}
                    aria-current={isActive ? "page" : undefined}
                    onClick={() => isMobile && setOpenMobile(false)}
                  >
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
  )
}

function initials(name: string | null): string {
  if (!name) return "?"
  const base = name.includes("@") ? name.split("@")[0] : name
  const parts = base.split(/[\s._-]+/).filter(Boolean)
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || base.slice(0, 2).toUpperCase()
}

/** Footer account menu: who is signed in, theme choice, extra links, sign out. */
export function UserMenu({
  userDisplay,
  subtitle,
  onSignOut,
  children,
}: {
  userDisplay: string | null
  subtitle?: string
  onSignOut: () => void
  /** Extra DropdownMenuItems rendered above the theme options. */
  children?: ReactNode
}) {
  const { theme, setTheme } = useTheme()
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" className="data-[state=open]:bg-sidebar-accent group-data-[collapsible=icon]:p-0!">
              <span
                aria-hidden
                className="flex size-8 shrink-0 items-center justify-center rounded-full border bg-card font-mono text-xs font-semibold text-foreground"
              >
                {initials(userDisplay)}
              </span>
              <span className="grid min-w-0 flex-1 text-left leading-tight">
                <span className="truncate text-sm font-medium">{userDisplay ?? "Signed in"}</span>
                {subtitle && <span className="truncate text-xs text-muted-foreground">{subtitle}</span>}
              </span>
              <ChevronsUpDown className="ml-auto size-4 text-muted-foreground" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-(--radix-dropdown-menu-trigger-width) min-w-56">
            <DropdownMenuLabel className="truncate font-normal text-muted-foreground">
              {userDisplay ?? "Signed in"}
            </DropdownMenuLabel>
            {children && (
              <>
                <DropdownMenuSeparator />
                {children}
              </>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="eyebrow py-1">Theme</DropdownMenuLabel>
            <DropdownMenuRadioGroup value={theme} onValueChange={(v) => setTheme(v as "light" | "dark" | "system")}>
              <DropdownMenuRadioItem value="light">
                <Sun className="size-4" /> Light
              </DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="dark">
                <Moon className="size-4" /> Dark
              </DropdownMenuRadioItem>
              <DropdownMenuRadioItem value="system">
                <Monitor className="size-4" /> System
              </DropdownMenuRadioItem>
            </DropdownMenuRadioGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={onSignOut}>
              <LogOut className="size-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

/** Full-width warning strip shown while a superadmin acts inside a tenant. */
export function ImpersonationBanner({ tenantSlug, onStop }: { tenantSlug: string; onStop: () => void }) {
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-warning/30 bg-warning/10 px-4 py-2 text-sm"
    >
      <UserCog className="size-4 shrink-0 text-warning" aria-hidden />
      <span className="min-w-0 flex-1">
        <span className="font-medium">Impersonating</span>{" "}
        <span className="font-mono text-[0.8125rem]">{tenantSlug}</span>
        <span className="hidden text-muted-foreground sm:inline"> — changes apply to this tenant.</span>
      </span>
      <Button variant="outline" size="xs" asChild>
        <Link to="/admin" onClick={onStop}>
          Stop impersonating
        </Link>
      </Button>
    </div>
  )
}
