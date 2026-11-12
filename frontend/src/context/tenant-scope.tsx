/**
 * TenantScope (SPEC Module 5): one set of tenant resource views serves both the
 * Tenant Dashboard (/:tenantSlug/*) and the Superadmin Console (/admin/tenants/:slug).
 * The scoped `api` client carries X-Tenant-Slug and, only when impersonating,
 * X-Impersonate-Tenant on every request. Context + useTenantScope live in tenant-scope-context.ts.
 */

import { useMemo, type ReactNode } from "react"
import { apiClient } from "@/lib/api-client"
import {
  TenantContext,
  getSwitchTenantUrl,
  type TenantContextValue,
} from "@/contexts/tenant-context"
import { TenantScopeContext, type TenantScopeValue } from "@/context/tenant-scope-context"

export function TenantScopeProvider({
  tenantSlug,
  isSuperadminImpersonating = false,
  basePath = `/${tenantSlug}`,
  embedded = false,
  children,
}: {
  tenantSlug: string
  isSuperadminImpersonating?: boolean
  basePath?: string
  /** See TenantScopeValue.embedded. */
  embedded?: boolean
  children: ReactNode
}) {
  const scope = useMemo<TenantScopeValue>(
    () => ({
      tenantSlug,
      isSuperadminImpersonating,
      basePath,
      embedded,
      api: apiClient.forTenant(tenantSlug, { impersonate: isSuperadminImpersonating }),
    }),
    [tenantSlug, isSuperadminImpersonating, basePath, embedded]
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
