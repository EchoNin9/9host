/**
 * API client for 9host backend.
 * Uses VITE_API_URL (set in CI from tofu output).
 */

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
      },
    })
    if (!res.ok) return null
    return (await res.json()) as AnalyticsResponse
  } catch {
    return null
  }
}
