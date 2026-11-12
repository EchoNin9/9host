/**
 * TenantScope (SPEC Module 5): one set of tenant resource views serves both the
 * Tenant Dashboard (/:tenantSlug/*) and the Superadmin Console (/admin/tenants/:slug).
 * The scoped `api` client carries X-Tenant-Slug and, only when impersonating,
 * X-Impersonate-Tenant on every request.
 */

import { createContext, useContext, useMemo, type ReactNode } from "react"
import { apiClient, type TenantApi } from "@/lib/api-client"
import {
  TenantContext,
  getSwitchTenantUrl,
  type TenantContextValue,
} from "@/contexts/tenant-context"

export interface TenantScopeValue {
  tenantSlug: string
  isSuperadminImpersonating: boolean
  /** Route prefix for this tenant's resource views (e.g. "/acme" or "/admin/tenants/acme"). */
  basePath: string
  api: TenantApi
}

const TenantScopeContext = createContext<TenantScopeValue | null>(null)

export function TenantScopeProvider({
  tenantSlug,
  isSuperadminImpersonating = false,
  basePath = `/${tenantSlug}`,
  children,
}: {
  tenantSlug: string
  isSuperadminImpersonating?: boolean
  basePath?: string
  children: ReactNode
}) {
  const scope = useMemo<TenantScopeValue>(
    () => ({
      tenantSlug,
      isSuperadminImpersonating,
      basePath,
      api: apiClient.forTenant(tenantSlug, { impersonate: isSuperadminImpersonating }),
    }),
    [tenantSlug, isSuperadminImpersonating, basePath]
  )
  // Keep useTenant() consumers (slug, base path) consistent with the scope.
  const tenant = useMemo<TenantContextValue>(
    () => ({
      tenantSlug,
      hasTenant: true,
      tenantBasePath: basePath,
      refresh: () => {},
      getSwitchTenantUrl: (newSlug: string) => getSwitchTenantUrl(newSlug, basePath),
    }),
    [tenantSlug, basePath]
  )
  return (
    <TenantScopeContext.Provider value={scope}>
      <TenantContext.Provider value={tenant}>{children}</TenantContext.Provider>
    </TenantScopeContext.Provider>
  )
}

export function useTenantScope(): TenantScopeValue {
  const ctx = useContext(TenantScopeContext)
  if (!ctx) throw new Error("useTenantScope must be used within TenantScopeProvider")
  return ctx
}
