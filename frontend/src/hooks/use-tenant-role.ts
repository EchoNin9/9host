"use client"

import { useTenant } from "@/hooks/use-tenant"
import { useTenants } from "@/hooks/use-tenants"
import { useImpersonation } from "@/hooks/use-impersonation"

/**
 * Returns the user's role in the current tenant and whether they can create/edit/delete.
 * admin and manager can mutate; editor and member cannot (Task 2.16).
 * When impersonating, superadmin can do everything.
 */
export function useTenantRole(): {
  role: string
  canEdit: boolean
} {
  const { tenantSlug } = useTenant()
  const { tenants } = useTenants()
  const { isImpersonating } = useImpersonation()

  const role =
    tenantSlug && tenants.length > 0
      ? (tenants.find((t) => t.slug === tenantSlug)?.role ?? "member")
      : "member"

  const canEdit =
    isImpersonating || role === "admin" || role === "manager"

  return { role, canEdit }
}
