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
