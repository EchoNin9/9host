/**
 * TenantScope context + hook (split from tenant-scope.tsx so that file only exports
 * components — react-refresh/only-export-components).
 */

import { createContext, useContext } from "react"
import type { TenantApi } from "@/lib/api-client"

export interface TenantScopeValue {
  tenantSlug: string
  isSuperadminImpersonating: boolean
  /** Route prefix for this tenant's resource views (e.g. "/acme" or "/admin/tenants/acme"). */
  basePath: string
  /** Rendered inside another page's chrome (Superadmin Console tabs): no outer padding, no <h1>. */
  embedded?: boolean
  api: TenantApi
}

export const TenantScopeContext = createContext<TenantScopeValue | null>(null)

export function useTenantScope(): TenantScopeValue {
  const ctx = useContext(TenantScopeContext)
  if (!ctx) throw new Error("useTenantScope must be used within TenantScopeProvider")
  return ctx
}
