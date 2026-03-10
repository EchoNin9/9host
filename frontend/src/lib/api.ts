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
  if (!base || !accessToken) return { tenants: [], isSuperadmin: false }

  try {
    const res = await fetch(`${base}/api/admin/tenants`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    })
    if (res.status === 403) return { tenants: [], isSuperadmin: false }
    if (!res.ok) return { tenants: [], isSuperadmin: false }
    const data = (await res.json()) as AdminTenantsResponse
    return {
      tenants: data.tenants ?? [],
      isSuperadmin: true,
    }
  } catch {
    return { tenants: [], isSuperadmin: false }
  }
}

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
  body: { name: string; slug?: string; status?: string }
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
