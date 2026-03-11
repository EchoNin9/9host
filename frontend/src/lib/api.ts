/**
 * API client for 9host backend.
 * Uses VITE_API_URL (set in CI from tofu output).
 *
 * Impersonation (Task 2.13): When setImpersonateTenant(slug) is called, all
 * tenant-scoped requests include X-Impersonate-Tenant header for superadmin.
 */

let _impersonateTenant: string | null = null

/** Set impersonation target (superadmin only). Call with null to clear. */
export function setImpersonateTenant(slug: string | null): void {
  _impersonateTenant = slug ? slug.trim().toLowerCase() : null
}

function getImpersonateHeader(): Record<string, string> {
  return _impersonateTenant ? { "X-Impersonate-Tenant": _impersonateTenant } : {}
}

function getApiUrl(): string {
  const url = import.meta.env.VITE_API_URL as string | undefined
  if (!url) return ""
  return url.replace(/\/$/, "")
}

export interface Tenant {
  slug: string
  name: string
  role: string
}

export interface TenantsResponse {
  tenants: Tenant[]
}

/** Admin tenant (from GET /api/admin/tenants) — no role, includes tier */
export interface AdminTenant {
  slug: string
  name: string
  tier: string
}

export interface AdminTenantsResponse {
  tenants: AdminTenant[]
}

export interface FetchAllTenantsResult {
  tenants: AdminTenant[]
  isSuperadmin: boolean
}

/**
 * Fetch all tenants (superadmin only). Returns { tenants: [], isSuperadmin: false } on 403.
 */
export async function fetchAllTenants(
  accessToken: string | null
): Promise<FetchAllTenantsResult> {
  const base = getApiUrl()
  const DBG = (msg: string, data?: unknown) =>
    console.log("[9host fetchAllTenants]", msg, data ?? "")

  if (!base || !accessToken) {
    DBG("early return", { hasBase: !!base, hasToken: !!accessToken })
    return { tenants: [], isSuperadmin: false }
  }

  try {
    DBG("fetching /api/admin/tenants")
    const res = await fetch(`${base}/api/admin/tenants`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    const body = await res.json().catch(() => ({}))
    DBG("response", { status: res.status, ok: res.ok, bodyKeys: Object.keys(body) })

    if (res.status === 403) {
      DBG("403 Forbidden - not superadmin")
      return { tenants: [], isSuperadmin: false }
    }
    if (!res.ok) {
      DBG("!res.ok", { status: res.status, error: (body as { error?: string }).error })
      return { tenants: [], isSuperadmin: false }
    }
    const data = body as AdminTenantsResponse
    return {
      tenants: data.tenants ?? [],
      isSuperadmin: true,
    }
  } catch (err) {
    DBG("catch", err)
    return { tenants: [], isSuperadmin: false }
  }
}

// -----------------------------------------------------------------------------
// Tenant metadata (GET /api/tenant)
// -----------------------------------------------------------------------------

/** Resolved features from GET /api/tenant (tier + module_overrides) */
export type ResolvedFeatures = Record<string, boolean>

export interface TenantMetadata {
  tenant_slug: string
  name: string
  tier: string
  owner_sub: string | null
  module_overrides?: Record<string, boolean>
  resolved_features?: ResolvedFeatures
  created_at?: string
  updated_at?: string
}

function tenantHeaders(tenantSlug: string, accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`,
    "X-Tenant-Slug": tenantSlug,
    ...getImpersonateHeader(),
  }
}

/**
 * Fetch tenant metadata (name, tier, owner_sub).
 */
export async function fetchTenant(
  tenantSlug: string,
  accessToken: string | null
): Promise<TenantMetadata | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return null

  try {
    const res = await fetch(`${base}/api/tenant`, {
      headers: tenantHeaders(tenantSlug, accessToken),
    })
    if (!res.ok) return null
    return (await res.json()) as TenantMetadata
  } catch {
    return null
  }
}

/**
 * Fetch single tenant by slug (superadmin only).
 */
export async function fetchAdminTenant(
  accessToken: string | null,
  slug: string
): Promise<AdminTenantDetail | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !slug) return null

  try {
    const res = await fetch(`${base}/api/admin/tenants/${encodeURIComponent(slug)}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!res.ok) return null
    return (await res.json()) as AdminTenantDetail
  } catch {
    return null
  }
}

/** Admin tenant detail (from GET /api/admin/tenants/{slug}) */
export interface AdminTenantDetail {
  slug: string
  name: string
  tier: string
  owner_sub?: string | null
  module_overrides?: Record<string, boolean>
  created_at?: string
  updated_at?: string
}

/**
 * PATCH tenant (superadmin only). Body: tier, name, module_overrides.
 */
export async function patchAdminTenant(
  accessToken: string | null,
  slug: string,
  body: { tier?: string; name?: string; module_overrides?: Record<string, boolean> }
): Promise<AdminTenantDetail | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !slug) return null

  try {
    const res = await fetch(`${base}/api/admin/tenants/${encodeURIComponent(slug)}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    return (await res.json()) as AdminTenantDetail
  } catch {
    return null
  }
}

/**
 * PATCH tenant module_overrides (admin/manager only). Task 2.22.
 */
export async function patchTenantModuleOverrides(
  tenantSlug: string,
  accessToken: string | null,
  module_overrides: Record<string, boolean>
): Promise<TenantMetadata | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return null

  try {
    const res = await fetch(`${base}/api/tenant`, {
      method: "PATCH",
      headers: {
        ...tenantHeaders(tenantSlug, accessToken),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ module_overrides }),
    })
    if (!res.ok) return null
    const data = (await res.json()) as TenantMetadata
    return data
  } catch {
    return null
  }
}

/**
 * Transfer tenant owner. Requires current user to be owner.
 */
export async function putTransferOwner(
  tenantSlug: string,
  accessToken: string | null,
  newOwnerSub: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !newOwnerSub) return false

  try {
    const res = await fetch(`${base}/api/tenant`, {
      method: "PUT",
      headers: {
        ...tenantHeaders(tenantSlug, accessToken),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ owner_sub: newOwnerSub }),
    })
    return res.ok
  } catch {
    return false
  }
}

// -----------------------------------------------------------------------------
// Tenant users (GET /api/tenant/users, permissions)
// -----------------------------------------------------------------------------

export interface TenantUser {
  sub: string
  email: string
  name: string
  role: string
  created_at?: string
  updated_at?: string
}

export interface TenantUsersResponse {
  users: TenantUser[]
}

export const MODULE_KEYS = ["sites", "domains", "analytics", "settings"] as const

export type ModulePermissions = Record<(typeof MODULE_KEYS)[number], boolean>

/**
 * Fetch tenants for the authenticated user.
 * Requires Authorization: Bearer <accessToken>.
 * Returns empty array on 401 or when API URL is not configured.
 */
export async function fetchTenants(accessToken: string | null): Promise<Tenant[]> {
  const base = getApiUrl()
  if (!base || !accessToken) return []

  try {
    const res = await fetch(`${base}/api/tenants`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    })
    if (res.status === 401) return []
    if (!res.ok) return []
    const data = (await res.json()) as TenantsResponse
    return data.tenants ?? []
  } catch {
    return []
  }
}

/**
 * Fetch tenant users (admin/manager only).
 */
export async function fetchTenantUsers(
  tenantSlug: string,
  accessToken: string | null
): Promise<TenantUser[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return []

  try {
    const res = await fetch(`${base}/api/tenant/users`, {
      headers: tenantHeaders(tenantSlug, accessToken),
    })
    if (!res.ok) return []
    const data = (await res.json()) as TenantUsersResponse
    return data.users ?? []
  } catch {
    return []
  }
}

/**
 * Fetch user permissions (admin/manager only).
 */
export async function fetchUserPermissions(
  tenantSlug: string,
  accessToken: string | null,
  userSub: string
): Promise<ModulePermissions | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !userSub) return null

  try {
    const res = await fetch(
      `${base}/api/tenant/users/${encodeURIComponent(userSub)}/permissions`,
      { headers: tenantHeaders(tenantSlug, accessToken) }
    )
    if (!res.ok) return null
    const data = (await res.json()) as { permissions: ModulePermissions }
    return data.permissions ?? null
  } catch {
    return null
  }
}

/**
 * Update user permissions (admin/manager only).
 */
export async function updateUserPermissions(
  tenantSlug: string,
  accessToken: string | null,
  userSub: string,
  permissions: Partial<ModulePermissions>
): Promise<ModulePermissions | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !userSub) return null

  try {
    const res = await fetch(
      `${base}/api/tenant/users/${encodeURIComponent(userSub)}/permissions`,
      {
        method: "PUT",
        headers: {
          ...tenantHeaders(tenantSlug, accessToken),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ permissions }),
      }
    )
    if (!res.ok) return null
    const data = (await res.json()) as { permissions: ModulePermissions }
    return data.permissions ?? null
  } catch {
    return null
  }
}

// -----------------------------------------------------------------------------
// Analytics (Pro+ tier)
// -----------------------------------------------------------------------------

export interface AnalyticsDataPoint {
  date: string
  count: number
}

export interface TopPage {
  path: string
  views: number
}

export interface AnalyticsResponse {
  period: string
  page_views_over_time: AnalyticsDataPoint[]
  total_page_views: number
  unique_visitors: number
  top_pages: TopPage[]
  placeholder?: boolean
}

/**
 * Fetch analytics for a tenant (Pro+ tier).
 * Requires tenant_slug (X-Tenant-Slug header), Authorization: Bearer <accessToken>.
 */
export async function fetchAnalytics(
  tenantSlug: string,
  accessToken: string | null
): Promise<AnalyticsResponse | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return null

  try {
    const res = await fetch(`${base}/api/tenant/analytics`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Tenant-Slug": tenantSlug,
        ...getImpersonateHeader(),
      },
    })
    if (!res.ok) return null
    return (await res.json()) as AnalyticsResponse
  } catch {
    return null
  }
}

// -----------------------------------------------------------------------------
// Sites (tenant-scoped CRUD)
// -----------------------------------------------------------------------------

export interface Site {
  id: string
  name: string
  slug: string
  status: string
  template_id?: string
  created_at: string
  updated_at: string
}

export interface SitesResponse {
  sites: Site[]
}

export interface SiteResponse {
  site: Site
}

function sitesHeaders(tenantSlug: string, accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
    "X-Tenant-Slug": tenantSlug,
    ...getImpersonateHeader(),
  }
}

/**
 * List sites for a tenant.
 */
export async function fetchSites(
  tenantSlug: string,
  accessToken: string | null
): Promise<Site[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return []

  try {
    const res = await fetch(`${base}/api/tenant/sites`, {
      headers: sitesHeaders(tenantSlug, accessToken),
    })
    if (!res.ok) return []
    const data = (await res.json()) as SitesResponse
    return data.sites ?? []
  } catch {
    return []
  }
}

/**
 * Create a site.
 */
export async function createSite(
  tenantSlug: string,
  accessToken: string | null,
  body: { name: string; slug?: string; status?: string; template_id?: string }
): Promise<Site | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return null

  try {
    const res = await fetch(`${base}/api/tenant/sites`, {
      method: "POST",
      headers: sitesHeaders(tenantSlug, accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const data = (await res.json()) as SiteResponse
    return data.site ?? null
  } catch {
    return null
  }
}

/**
 * Update a site.
 */
export async function updateSite(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  body: { name?: string; slug?: string; status?: string }
): Promise<Site | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId) return null

  try {
    const res = await fetch(`${base}/api/tenant/sites/${siteId}`, {
      method: "PUT",
      headers: sitesHeaders(tenantSlug, accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const data = (await res.json()) as SiteResponse
    return data.site ?? null
  } catch {
    return null
  }
}

/**
 * Delete a site.
 */
export async function deleteSite(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId) return false

  try {
    const res = await fetch(`${base}/api/tenant/sites/${siteId}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Tenant-Slug": tenantSlug,
        ...getImpersonateHeader(),
      },
    })
    return res.status === 204
  } catch {
    return false
  }
}

// -----------------------------------------------------------------------------
// Domains (Pro+ tier, tenant-scoped)
// -----------------------------------------------------------------------------

export interface Domain {
  domain: string
  site_id: string
  status: string
  created_at: string
  updated_at: string
}

export interface DomainsResponse {
  domains: Domain[]
}

export interface DomainResponse {
  domain: Domain
}

function domainsHeaders(tenantSlug: string, accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
    "X-Tenant-Slug": tenantSlug,
    ...getImpersonateHeader(),
  }
}

/**
 * List domains for a tenant (Pro+ tier).
 */
export async function fetchDomains(
  tenantSlug: string,
  accessToken: string | null
): Promise<Domain[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return []

  try {
    const res = await fetch(`${base}/api/tenant/domains`, {
      headers: domainsHeaders(tenantSlug, accessToken),
    })
    if (!res.ok) return []
    const data = (await res.json()) as DomainsResponse
    return data.domains ?? []
  } catch {
    return []
  }
}

/**
 * Add a custom domain (Pro+ tier).
 */
export async function createDomain(
  tenantSlug: string,
  accessToken: string | null,
  body: { domain: string; site_id: string; status?: string }
): Promise<Domain | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return null

  try {
    const res = await fetch(`${base}/api/tenant/domains`, {
      method: "POST",
      headers: domainsHeaders(tenantSlug, accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const data = (await res.json()) as DomainResponse
    return data.domain ?? null
  } catch {
    return null
  }
}

/**
 * Remove a custom domain (Pro+ tier).
 */
export async function deleteDomain(
  tenantSlug: string,
  accessToken: string | null,
  domain: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !domain) return false

  try {
    const res = await fetch(`${base}/api/tenant/domains/${encodeURIComponent(domain)}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "X-Tenant-Slug": tenantSlug,
        ...getImpersonateHeader(),
      },
    })
    return res.status === 204
  } catch {
    return false
  }
}

// -----------------------------------------------------------------------------
// Admin templates (superadmin only)
// -----------------------------------------------------------------------------

export interface Template {
  slug: string
  name: string
  description: string
  tier_required: string
  components: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface TemplatesResponse {
  templates: Template[]
}

export async function fetchTemplates(
  tenantSlug: string,
  accessToken: string | null
): Promise<Template[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return []

  try {
    const res = await fetch(`${base}/api/templates`, {
      headers: tenantHeaders(tenantSlug, accessToken),
    })
    if (!res.ok) return []
    const data = (await res.json()) as TemplatesResponse
    return data.templates ?? []
  } catch {
    return []
  }
}

export interface AdminTemplate {
  slug: string
  name: string
  description: string
  tier_required: string
  components: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface AdminTemplatesResponse {
  templates: AdminTemplate[]
}

function adminHeaders(accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
  }
}

export async function fetchAdminTemplates(
  accessToken: string | null
): Promise<AdminTemplate[]> {
  const base = getApiUrl()
  if (!base || !accessToken) return []

  try {
    const res = await fetch(`${base}/api/admin/templates`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!res.ok) return []
    const data = (await res.json()) as AdminTemplatesResponse
    return data.templates ?? []
  } catch {
    return []
  }
}

export async function fetchAdminTemplate(
  accessToken: string | null,
  slug: string
): Promise<AdminTemplate | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !slug) return null

  try {
    const res = await fetch(`${base}/api/admin/templates/${encodeURIComponent(slug)}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!res.ok) return null
    return (await res.json()) as AdminTemplate
  } catch {
    return null
  }
}

export async function createAdminTemplate(
  accessToken: string | null,
  body: { slug: string; name: string; description?: string; tier_required?: string; components?: Record<string, unknown> }
): Promise<AdminTemplate | null> {
  const base = getApiUrl()
  if (!base || !accessToken) return null

  try {
    const res = await fetch(`${base}/api/admin/templates`, {
      method: "POST",
      headers: adminHeaders(accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    return (await res.json()) as AdminTemplate
  } catch {
    return null
  }
}

export async function updateAdminTemplate(
  accessToken: string | null,
  slug: string,
  body: { name?: string; description?: string; tier_required?: string; components?: Record<string, unknown> }
): Promise<AdminTemplate | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !slug) return null

  try {
    const res = await fetch(`${base}/api/admin/templates/${encodeURIComponent(slug)}`, {
      method: "PUT",
      headers: adminHeaders(accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    return (await res.json()) as AdminTemplate
  } catch {
    return null
  }
}

export async function deleteAdminTemplate(
  accessToken: string | null,
  slug: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !slug) return false

  try {
    const res = await fetch(`${base}/api/admin/templates/${encodeURIComponent(slug)}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    return res.ok
  } catch {
    return false
  }
}
