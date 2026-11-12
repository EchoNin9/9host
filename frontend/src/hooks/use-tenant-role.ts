"use client"

import { useTenant } from "@/hooks/use-tenant"
import { useTenants } from "@/hooks/use-tenants"
import { useTenantScope } from "@/context/tenant-scope-context"
import { getAuthMode, readSiteToken } from "@/lib/api-client"

/** Role claim from the site-login JWT. Display only; the backend stays the authority. */
function siteTokenRole(): string {
  try {
    const payload = readSiteToken()?.split(".")[1]
    if (!payload) return "member"
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"))
    const role = JSON.parse(json).role
    return typeof role === "string" ? role : "member"
  } catch {
    return "member"
  }
}

/**
 * Returns the user's role in the current tenant and whether they can create/edit/delete.
 * admin and manager can mutate; member cannot (Task 2.16).
 * When impersonating, superadmin can do everything.
 */
export function useTenantRole(): {
  role: string
  canEdit: boolean
} {
  const { tenantSlug } = useTenant()
  const { tenants } = useTenants()
  const { isSuperadminImpersonating } = useTenantScope()

  const role =
    getAuthMode() === "tuser"
      ? siteTokenRole()
      : tenantSlug && tenants.length > 0
        ? (tenants.find((t) => t.slug === tenantSlug)?.role ?? "member")
        : "member"

  const canEdit =
    isSuperadminImpersonating || role === "admin" || role === "manager"

  return { role, canEdit }
}
