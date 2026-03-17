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

/** Storage key for site-login JWT (non-Cognito tenant user). */
export const SITE_TOKEN_KEY = "9host-site-token"

/** Site login response from POST /api/auth/site-login */
export interface SiteLoginResponse {
  token: string
  tenant_slug: string
  role: string
  username?: string
  display_name?: string
}

/** Storage key for site user display (username or display_name). */
export const SITE_USER_DISPLAY_KEY = "9host-site-user-display"

/**
 * Get auth token for API calls. Returns site JWT if present, else Cognito access token.
 * Use this for all tenant-scoped and admin API requests.
 */
export async function getToken(): Promise<string | null> {
  const siteToken = localStorage.getItem(SITE_TOKEN_KEY)
  if (siteToken) return siteToken
  try {
    const { fetchAuthSession } = await import("aws-amplify/auth")
    const session = await fetchAuthSession()
    return session.tokens?.accessToken?.toString() ?? null
  } catch {
    return null
  }
}

/** Check if user is authenticated via site login (non-Cognito). */
export function isSiteUser(): boolean {
  return !!localStorage.getItem(SITE_TOKEN_KEY)
}

/** Clear site token and user display (call on sign out for site users). */
export function clearSiteToken(): void {
  localStorage.removeItem(SITE_TOKEN_KEY)
  localStorage.removeItem(SITE_USER_DISPLAY_KEY)
}

/** Get site user display string (display_name or username). Returns null if not a site user. */
export function getSiteUserDisplay(): string | null {
  if (!isSiteUser()) return null
  return localStorage.getItem(SITE_USER_DISPLAY_KEY)
}

export type SiteLoginResult =
  | { ok: true; data: SiteLoginResponse }
  | { ok: false; error: string; status?: number }

/**
 * Site login — authenticate non-Cognito tenant user.
 * Returns { ok: true, data } on success.
 * Returns { ok: false, error, status } on failure (status 503 = service unavailable).
 */
export async function siteLogin(
  body: { username: string; password: string; site: string }
): Promise<SiteLoginResult> {
  const base = getApiUrl()
  if (!base) {
    return { ok: false, error: "API not configured", status: 0 }
  }

  try {
    const res = await fetch(`${base}/api/auth/site-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    if (res.ok) {
      const data = (await res.json()) as SiteLoginResponse
      return { ok: true, data }
    }
    const status = res.status
    if (status === 503) {
      return { ok: false, error: "Service unavailable", status }
    }
    return { ok: false, error: "Invalid username, password, or site", status }
  } catch {
    return { ok: false, error: "Network error", status: 0 }
  }
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

export interface AdminStats {
  total_users: number
  total_tenants: number
  total_cognito_users: number
  total_tenant_users: number
}

export interface AdminUserItem {
  type: "cognito" | "tenant_user"
  sub?: string
  username?: string
  email?: string | null
  name?: string
  display_name?: string
  role: string
}

export interface AdminUsersResponse {
  users_by_tenant: Record<string, AdminUserItem[]>
  orphaned: AdminUserItem[]
}

/**
 * Fetch all users across tenants (superadmin only). GET /api/admin/users
 */
export async function fetchAdminUsers(
  accessToken: string | null
): Promise<AdminUsersResponse | null> {
  const base = getApiUrl()
  if (!base || !accessToken) return null

  try {
    const res = await fetch(`${base}/api/admin/users`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!res.ok) return null
    return (await res.json()) as AdminUsersResponse
  } catch {
    return null
  }
}

/**
 * Fetch admin stats (superadmin only). GET /api/admin/stats
 */
export async function fetchAdminStats(
  accessToken: string | null
): Promise<AdminStats | null> {
  const base = getApiUrl()
  if (!base || !accessToken) return null

  try {
    const res = await fetch(`${base}/api/admin/stats`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!res.ok) return null
    return (await res.json()) as AdminStats
  } catch {
    return null
  }
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
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    // #region agent log
    if (!res.ok) {
      const bodyText = await res.text()
      let bodyJson: unknown = null
      try {
        bodyJson = bodyText ? JSON.parse(bodyText) : null
      } catch {
        bodyJson = bodyText
      }
      console.warn('[9host debug] fetchAllTenants failed:',{status:res.status,hasToken:!!accessToken,body:bodyJson})
    }
    // #endregion
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
 * Fetch default site ID for tenant (Task 1.98). Public — no auth required.
 * Returns { site_id } or null if no default site published.
 */
export async function fetchDefaultSite(tenantSlug: string): Promise<{ site_id: string } | null> {
  const base = getApiUrl()
  if (!base || !tenantSlug) return null

  try {
    const res = await fetch(`${base}/api/tenant/default-site`, {
      headers: { "X-Tenant-Slug": tenantSlug },
    })
    if (!res.ok) return null
    return (await res.json()) as { site_id: string }
  } catch {
    return null
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
    if (!res.ok) {
      if (res.status === 500) {
        const body = await res.json().catch(() => ({}))
        console.error("[9host] GET /api/tenant 500:", body)
      }
      return null
    }
    return (await res.json()) as TenantMetadata
  } catch {
    return null
  }
}

/**
 * Create tenant (superadmin only). Body: slug (max 60 chars), name, tier.
 */
export async function createAdminTenant(
  accessToken: string | null,
  body: { slug: string; name: string; tier?: string }
): Promise<AdminTenantDetail | null> {
  const base = getApiUrl()
  if (!base || !accessToken) return null

  try {
    const res = await fetch(`${base}/api/admin/tenants`, {
      method: "POST",
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
  owner_email?: string | null
  module_overrides?: Record<string, boolean>
  created_at?: string
  updated_at?: string
}

/**
 * DELETE tenant (superadmin only). Cascade-deletes all sub-resources.
 */
export async function deleteAdminTenant(
  accessToken: string | null,
  slug: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !slug) return false
  try {
    const res = await fetch(`${base}/api/admin/tenants/${encodeURIComponent(slug)}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    return res.status === 204
  } catch {
    return false
  }
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
  type?: string
}

export interface TenantUsersResponse {
  users: TenantUser[]
}

export const MODULE_KEYS = ["sites", "domains", "analytics", "settings", "users"] as const

export type ModulePermissions = Record<(typeof MODULE_KEYS)[number], boolean>

/** Non-Cognito tenant user (TUSER) */
export interface TenantTUser {
  username: string
  display_name: string
  role: string
  created_at?: string
  updated_at?: string
}

/** Custom role for tenant */
export interface TenantRole {
  name: string
  permissions: Record<string, boolean>
  created_at?: string
  updated_at?: string
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

/** Self-serve tenant creation response (Task 4.1) */
export interface CreateTenantResponse {
  slug: string
  name: string
  tier: string
  owner_sub?: string
  created_at?: string
  updated_at?: string
}

/**
 * Create tenant (self-serve). Body: slug (max 60 chars), name (optional).
 * Requires Cognito auth. Tier is always FREE.
 * Returns created tenant on success, null on failure.
 */
export async function createTenant(
  accessToken: string | null,
  body: { slug: string; name?: string }
): Promise<CreateTenantResponse | null> {
  const base = getApiUrl()
  if (!base || !accessToken) return null

  try {
    const res = await fetch(`${base}/api/tenants`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    return (await res.json()) as CreateTenantResponse
  } catch {
    return null
  }
}

/**
 * Create tenant with error details. Returns { ok: true, data } or { ok: false, error, status }.
 */
export async function createTenantWithError(
  accessToken: string | null,
  body: { slug: string; name?: string }
): Promise<
  | { ok: true; data: CreateTenantResponse }
  | { ok: false; error: string; status?: number }
> {
  const base = getApiUrl()
  if (!base || !accessToken) {
    return { ok: false, error: "Not authenticated", status: 401 }
  }

  try {
    const res = await fetch(`${base}/api/tenants`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })
    if (res.ok) {
      const data = (await res.json()) as CreateTenantResponse
      return { ok: true, data }
    }
    const errBody = await res.json().catch(() => ({}))
    const msg = (errBody as { error?: string }).error ?? res.statusText
    return { ok: false, error: msg, status: res.status }
  } catch {
    return { ok: false, error: "Network error", status: 0 }
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
// Non-Cognito tenant users (TUSER) and custom roles
// -----------------------------------------------------------------------------

/**
 * Fetch non-Cognito tenant users (admin/manager only).
 */
export async function fetchTenantTUsers(
  tenantSlug: string,
  accessToken: string | null
): Promise<TenantTUser[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return []

  try {
    const res = await fetch(`${base}/api/tenant/tusers`, {
      headers: tenantHeaders(tenantSlug, accessToken),
    })
    if (!res.ok) return []
    const data = (await res.json()) as { users: TenantTUser[] }
    return data.users ?? []
  } catch {
    return []
  }
}

/**
 * Create non-Cognito tenant user (admin/manager only).
 */
export async function createTenantTUser(
  tenantSlug: string,
  accessToken: string | null,
  body: { username: string; password: string; display_name?: string; role: string }
): Promise<TenantTUser | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return null

  try {
    const res = await fetch(`${base}/api/tenant/tusers`, {
      method: "POST",
      headers: {
        ...tenantHeaders(tenantSlug, accessToken),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const data = (await res.json()) as { user: TenantTUser }
    return data.user ?? null
  } catch {
    return null
  }
}

/**
 * Update non-Cognito tenant user (admin/manager only).
 */
export async function updateTenantTUser(
  tenantSlug: string,
  accessToken: string | null,
  username: string,
  body: { role?: string; display_name?: string; password?: string }
): Promise<TenantTUser | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !username) return null

  try {
    const res = await fetch(
      `${base}/api/tenant/tusers/${encodeURIComponent(username)}`,
      {
        method: "PUT",
        headers: {
          ...tenantHeaders(tenantSlug, accessToken),
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      }
    )
    if (!res.ok) return null
    const data = (await res.json()) as { user: TenantTUser }
    return data.user ?? null
  } catch {
    return null
  }
}

/**
 * Delete non-Cognito tenant user (admin/manager only).
 */
export async function deleteTenantTUser(
  tenantSlug: string,
  accessToken: string | null,
  username: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !username) return false

  try {
    const res = await fetch(
      `${base}/api/tenant/tusers/${encodeURIComponent(username)}`,
      {
        method: "DELETE",
        headers: tenantHeaders(tenantSlug, accessToken),
      }
    )
    return res.ok
  } catch {
    return false
  }
}

/**
 * Fetch custom roles for tenant (admin/manager only).
 */
export async function fetchTenantRoles(
  tenantSlug: string,
  accessToken: string | null
): Promise<TenantRole[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return []

  try {
    const res = await fetch(`${base}/api/tenant/roles`, {
      headers: tenantHeaders(tenantSlug, accessToken),
    })
    if (!res.ok) return []
    const data = (await res.json()) as { roles: TenantRole[] }
    return data.roles ?? []
  } catch {
    return []
  }
}

/**
 * Create custom role (admin/manager only).
 */
export async function createTenantRole(
  tenantSlug: string,
  accessToken: string | null,
  body: { name: string; permissions: Record<string, boolean> }
): Promise<TenantRole | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return null

  try {
    const res = await fetch(`${base}/api/tenant/roles`, {
      method: "POST",
      headers: {
        ...tenantHeaders(tenantSlug, accessToken),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const data = (await res.json()) as { role: TenantRole }
    return data.role ?? null
  } catch {
    return null
  }
}

/**
 * Update custom role (admin/manager only).
 */
export async function updateTenantRole(
  tenantSlug: string,
  accessToken: string | null,
  roleName: string,
  body: { permissions: Record<string, boolean> }
): Promise<TenantRole | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !roleName) return null

  try {
    const res = await fetch(
      `${base}/api/tenant/roles/${encodeURIComponent(roleName)}`,
      {
        method: "PUT",
        headers: {
          ...tenantHeaders(tenantSlug, accessToken),
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      }
    )
    if (!res.ok) return null
    const data = (await res.json()) as { role: TenantRole }
    return data.role ?? null
  } catch {
    return null
  }
}

/**
 * Delete custom role (admin/manager only). Fails if users are assigned.
 */
export async function deleteTenantRole(
  tenantSlug: string,
  accessToken: string | null,
  roleName: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !roleName) return false

  try {
    const res = await fetch(
      `${base}/api/tenant/roles/${encodeURIComponent(roleName)}`,
      {
        method: "DELETE",
        headers: tenantHeaders(tenantSlug, accessToken),
      }
    )
    return res.ok
  } catch {
    return false
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

export interface SiteBranding {
  logo_s3_key?: string
  primary_color?: string
  font_family?: string
}

export interface Site {
  id: string
  name: string
  slug: string
  status: string
  template_id?: string
  branding?: SiteBranding
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
    // #region agent log
    if (!res.ok) {
      const bodyText = await res.text()
      let bodyJson: unknown = null
      try {
        bodyJson = bodyText ? JSON.parse(bodyText) : null
      } catch {
        bodyJson = bodyText
      }
      console.warn('[9host debug] fetchSites failed:',{status:res.status,tenantSlug,hasToken:!!accessToken,body:bodyJson})
    }
    // #endregion
    if (!res.ok) return []
    const data = (await res.json()) as SitesResponse
    return data.sites ?? []
  } catch (e) {
    // #region agent log
    console.warn('[9host debug] fetchSites threw:',{error:String(e)})
    // #endregion
    return []
  }
}

/**
 * Create a site.
 */
export async function createSite(
  tenantSlug: string,
  accessToken: string | null,
  body: { name: string; slug?: string; status?: string; template_id?: string | null }
): Promise<Site | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return null

  const payload = { ...body }
  if (payload.template_id === null) delete payload.template_id

  try {
    const res = await fetch(`${base}/api/tenant/sites`, {
      method: "POST",
      headers: sitesHeaders(tenantSlug, accessToken),
      body: JSON.stringify(payload),
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
  body: {
    name?: string
    slug?: string
    status?: string
    template_id?: string | null
    branding?: SiteBranding | null
  }
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
 * Validate site slug availability (Task 1.77).
 * GET /api/validate-slug?slug={slug}&exclude_site_id={id}
 */
export interface ValidateSlugResponse {
  available: boolean
  slug: string
}

export async function validateSlug(
  tenantSlug: string,
  accessToken: string | null,
  slug: string,
  excludeSiteId?: string | null
): Promise<ValidateSlugResponse | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !slug?.trim()) return null

  const params = new URLSearchParams({ slug: slug.trim().toLowerCase() })
  if (excludeSiteId) params.set("exclude_site_id", excludeSiteId)

  try {
    const res = await fetch(`${base}/api/validate-slug?${params}`, {
      headers: tenantHeaders(tenantSlug, accessToken),
    })
    if (!res.ok) return null
    return (await res.json()) as ValidateSlugResponse
  } catch {
    return null
  }
}

/**
 * Fetch site preview (Task 1.79). GET /api/tenant/sites/{id}/preview?template={slug}
 */
export interface SitePreviewData {
  id: string
  name: string
  slug: string
  status: string
  template_slug?: string
  template_name?: string
  components?: {
    pages?: string[]
    sections?: Record<string, string[]>
    defaults?: Record<string, string>
  }
}

export async function fetchSitePreview(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  templateSlug?: string | null
): Promise<SitePreviewData | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId) return null

  const params = new URLSearchParams()
  if (templateSlug) params.set("template", templateSlug)
  const qs = params.toString()

  try {
    const res = await fetch(
      `${base}/api/tenant/sites/${encodeURIComponent(siteId)}/preview${qs ? `?${qs}` : ""}`,
      { headers: sitesHeaders(tenantSlug, accessToken) }
    )
    if (!res.ok) return null
    const data = (await res.json()) as { preview: SitePreviewData }
    return data.preview ?? null
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
  /** Task 1.81: CNAME target for DNS verification */
  verification_cname_target?: string
  /** Task 1.81: TXT record for ownership verification */
  verification_txt_record?: string
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
// Admin-scoped tenant sub-resources (superadmin only)
// -----------------------------------------------------------------------------

function adminResourceHeaders(accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
  }
}

function adminBase(tenantSlug: string) {
  return `${getApiUrl()}/api/admin/tenants/${encodeURIComponent(tenantSlug)}`
}

/** Admin domains: list, add, remove */
export async function fetchAdminDomains(
  accessToken: string | null,
  tenantSlug: string
): Promise<Domain[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return []
  try {
    const res = await fetch(`${adminBase(tenantSlug)}/domains`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!res.ok) return []
    const data = (await res.json()) as DomainsResponse
    return data.domains ?? []
  } catch {
    return []
  }
}

export async function createAdminDomain(
  accessToken: string | null,
  tenantSlug: string,
  body: { domain: string; site_id: string; status?: string }
): Promise<Domain | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return null
  try {
    const res = await fetch(`${adminBase(tenantSlug)}/domains`, {
      method: "POST",
      headers: adminResourceHeaders(accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const data = (await res.json()) as DomainResponse
    return data.domain ?? null
  } catch {
    return null
  }
}

export async function deleteAdminDomain(
  accessToken: string | null,
  tenantSlug: string,
  domain: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !domain) return false
  try {
    const res = await fetch(
      `${adminBase(tenantSlug)}/domains/${encodeURIComponent(domain)}`,
      { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } }
    )
    return res.status === 204
  } catch {
    return false
  }
}

/** Admin sites: list, create, update, delete */
export async function fetchAdminSites(
  accessToken: string | null,
  tenantSlug: string
): Promise<Site[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return []
  try {
    const res = await fetch(`${adminBase(tenantSlug)}/sites`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!res.ok) return []
    const data = (await res.json()) as SitesResponse
    return data.sites ?? []
  } catch {
    return []
  }
}

export async function createAdminSite(
  accessToken: string | null,
  tenantSlug: string,
  body: { name: string; slug?: string; status?: string; template_id?: string }
): Promise<{ site?: Site; error?: string } | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return null
  try {
    const res = await fetch(`${adminBase(tenantSlug)}/sites`, {
      method: "POST",
      headers: adminResourceHeaders(accessToken),
      body: JSON.stringify(body),
    })
    const data = await res.json()
    if (!res.ok) {
      return { error: data.error || "Failed to create site" }
    }
    return { site: data.site }
  } catch (e: any) {
    return { error: e.message || "Network error" }
  }
}

export async function updateAdminSite(
  accessToken: string | null,
  tenantSlug: string,
  siteId: string,
  body: { name?: string; slug?: string; status?: string }
): Promise<{ site?: Site; error?: string } | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId) return null
  try {
    const res = await fetch(`${adminBase(tenantSlug)}/sites/${siteId}`, {
      method: "PUT",
      headers: adminResourceHeaders(accessToken),
      body: JSON.stringify(body),
    })
    const data = await res.json()
    if (!res.ok) {
      return { error: data.error || "Failed to update site" }
    }
    return { site: data.site }
  } catch (e: any) {
    return { error: e.message || "Network error" }
  }
}

export async function deleteAdminSite(
  accessToken: string | null,
  tenantSlug: string,
  siteId: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId) return false
  try {
    const res = await fetch(`${adminBase(tenantSlug)}/sites/${siteId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    return res.status === 204
  } catch {
    return false
  }
}

/** Admin tenant users: list users in a tenant (superadmin). GET /api/admin/tenants/{slug}/users */
export async function fetchAdminTenantUsers(
  accessToken: string | null,
  tenantSlug: string
): Promise<TenantUser[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return []
  try {
    const res = await fetch(`${adminBase(tenantSlug)}/users`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!res.ok) return []
    const data = (await res.json()) as TenantUsersResponse
    return data.users ?? []
  } catch {
    return []
  }
}

export type CreateAdminUserResult =
  | { success: true; user: TenantUser }
  | { success: false; error: string }

/** Create Cognito user (email/role) or TUSER (type: "tuser", username, password, display_name, role). */
export async function createAdminUser(
  accessToken: string | null,
  tenantSlug: string,
  body:
    | { sub?: string; email?: string; role?: string; name?: string }
    | { type: "tuser"; username: string; password: string; display_name?: string; role: string }
): Promise<CreateAdminUserResult> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) {
    return { success: false, error: "Not configured" }
  }
  try {
    const res = await fetch(`${adminBase(tenantSlug)}/users`, {
      method: "POST",
      headers: adminResourceHeaders(accessToken),
      body: JSON.stringify(body),
    })
    const data = (await res.json()) as { user?: TenantUser; error?: string }
    if (!res.ok) {
      return { success: false, error: data.error ?? `Request failed (${res.status})` }
    }
    return data.user ? { success: true, user: data.user } : { success: false, error: "No user returned" }
  } catch (e) {
    return { success: false, error: e instanceof Error ? e.message : "Failed to add user" }
  }
}

/** Fetch custom roles for tenant (superadmin). GET /api/admin/tenants/{slug}/roles */
export async function fetchAdminTenantRoles(
  accessToken: string | null,
  tenantSlug: string
): Promise<TenantRole[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return []
  try {
    const res = await fetch(`${adminBase(tenantSlug)}/roles`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    if (!res.ok) return []
    const data = (await res.json()) as { roles: TenantRole[] }
    return data.roles ?? []
  } catch {
    return []
  }
}

export async function updateAdminUser(
  accessToken: string | null,
  tenantSlug: string,
  userSub: string,
  body: { role?: string; email?: string; name?: string }
): Promise<TenantUser | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !userSub) return null
  try {
    const res = await fetch(
      `${adminBase(tenantSlug)}/users/${encodeURIComponent(userSub)}`,
      {
        method: "PUT",
        headers: adminResourceHeaders(accessToken),
        body: JSON.stringify(body),
      }
    )
    if (!res.ok) return null
    const data = (await res.json()) as { user: TenantUser }
    return data.user ?? null
  } catch {
    return null
  }
}

export async function deleteAdminUser(
  accessToken: string | null,
  tenantSlug: string,
  userSub: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !userSub) return false
  try {
    const res = await fetch(
      `${adminBase(tenantSlug)}/users/${encodeURIComponent(userSub)}`,
      { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } }
    )
    return res.status === 204
  } catch {
    return false
  }
}

export async function fetchAdminUserPermissions(
  accessToken: string | null,
  tenantSlug: string,
  userSub: string
): Promise<ModulePermissions | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !userSub) return null
  try {
    const res = await fetch(
      `${adminBase(tenantSlug)}/users/${encodeURIComponent(userSub)}/permissions`,
      { headers: { Authorization: `Bearer ${accessToken}` } }
    )
    if (!res.ok) return null
    const data = (await res.json()) as { permissions: ModulePermissions }
    return data.permissions ?? null
  } catch {
    return null
  }
}

export async function updateAdminUserPermissions(
  accessToken: string | null,
  tenantSlug: string,
  userSub: string,
  permissions: Partial<ModulePermissions>
): Promise<ModulePermissions | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !userSub) return null
  try {
    const res = await fetch(
      `${adminBase(tenantSlug)}/users/${encodeURIComponent(userSub)}/permissions`,
      {
        method: "PUT",
        headers: adminResourceHeaders(accessToken),
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

/** Admin settings: update tenant tier, name, module_overrides, owner_sub */
export async function putAdminTenantSettings(
  accessToken: string | null,
  tenantSlug: string,
  body: {
    tier?: string
    name?: string
    module_overrides?: Record<string, boolean>
    owner_sub?: string | null
  }
): Promise<AdminTenantDetail | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) return null
  try {
    const res = await fetch(`${adminBase(tenantSlug)}/settings`, {
      method: "PUT",
      headers: adminResourceHeaders(accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    return (await res.json()) as AdminTenantDetail
  } catch {
    return null
  }
}

// -----------------------------------------------------------------------------
// Billing (Stripe Checkout + Customer Portal) — Task 3.1
// -----------------------------------------------------------------------------

export interface BillingCheckoutResponse {
  url: string
  session_id: string
}

export interface BillingPortalResponse {
  url: string
}

export type BillingCheckoutResult =
  | { ok: true; url: string; session_id: string }
  | { ok: false; error: string }

/**
 * Create Stripe Checkout Session for subscription. Redirect user to returned url.
 */
export async function createBillingCheckout(
  tenantSlug: string,
  accessToken: string | null,
  body: { tier: "pro" | "business"; success_url: string; cancel_url: string }
): Promise<BillingCheckoutResult> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) {
    return { ok: false, error: "API or auth not configured." }
  }

  try {
    const res = await fetch(`${base}/api/tenant/billing/checkout`, {
      method: "POST",
      headers: {
        ...tenantHeaders(tenantSlug, accessToken),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })
    const data = (await res.json()) as BillingCheckoutResponse | { error?: string }
    if (res.ok && "url" in data && data.url) {
      return { ok: true, url: data.url, session_id: data.session_id }
    }
    return {
      ok: false,
      error: (data as { error?: string }).error ?? "Failed to start checkout.",
    }
  } catch {
    return { ok: false, error: "Network error." }
  }
}

export type BillingPortalResult =
  | { ok: true; url: string }
  | { ok: false; error: string }

/**
 * Create Stripe Customer Portal session. Redirect user to returned url.
 */
export async function createBillingPortal(
  tenantSlug: string,
  accessToken: string | null,
  body: { return_url: string }
): Promise<BillingPortalResult> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug) {
    return { ok: false, error: "API or auth not configured." }
  }

  try {
    const res = await fetch(`${base}/api/tenant/billing/portal`, {
      method: "POST",
      headers: {
        ...tenantHeaders(tenantSlug, accessToken),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })
    const data = (await res.json()) as BillingPortalResponse | { error?: string }
    if (res.ok && "url" in data && data.url) {
      return { ok: true, url: data.url }
    }
    return {
      ok: false,
      error: (data as { error?: string }).error ?? "Failed to open billing portal.",
    }
  } catch {
    return { ok: false, error: "Network error." }
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

export type CreateAdminTemplateResult =
  | { success: true; template: AdminTemplate }
  | { success: false; error: string }

export async function createAdminTemplate(
  accessToken: string | null,
  body: { slug: string; name: string; description?: string; tier_required?: string; components?: Record<string, unknown> }
): Promise<CreateAdminTemplateResult> {
  const base = getApiUrl()
  if (!base || !accessToken) return { success: false, error: "Not configured" }

  try {
    const res = await fetch(`${base}/api/admin/templates`, {
      method: "POST",
      headers: adminHeaders(accessToken),
      body: JSON.stringify(body),
    })
    const data = (await res.json()) as AdminTemplate | { error?: string }
    if (!res.ok) {
      const msg = (data as { error?: string }).error ?? `Request failed (${res.status})`
      return { success: false, error: msg }
    }
    return { success: true, template: data as AdminTemplate }
  } catch (e) {
    return { success: false, error: e instanceof Error ? e.message : "Failed to create template" }
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

// -----------------------------------------------------------------------------
// Content API (posts, events, media, pages) — Task 1.95
// -----------------------------------------------------------------------------

export interface ContentPost {
  id: string
  slug: string
  title: string
  body: string
  status: string
  published_at?: string | null
  created_at: string
  updated_at: string
}

export interface ContentEvent {
  id: string
  title: string
  event_date: string
  venue: string
  location: string
  status: string
  published_at?: string | null
  created_at: string
  updated_at: string
}

export interface ContentMedia {
  id: string
  s3_key: string
  caption: string
  sort_order?: number | null
  status: string
  published_at?: string | null
  created_at: string
  updated_at: string
}

export interface ContentPage {
  path: string
  title: string
  body: string
  status: string
  published_at?: string | null
  created_at: string
  updated_at: string
}

function contentHeaders(tenantSlug: string, accessToken: string) {
  return {
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
    "X-Tenant-Slug": tenantSlug,
    ...getImpersonateHeader(),
  }
}

function contentBase(_tenantSlug: string, siteId: string) {
  return `${getApiUrl()}/api/tenant/sites/${encodeURIComponent(siteId)}`
}

export async function fetchContentPosts(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string
): Promise<ContentPost[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId) return []
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/posts`, {
      headers: contentHeaders(tenantSlug, accessToken),
    })
    if (!res.ok) return []
    const data = (await res.json()) as { posts: ContentPost[] }
    return data.posts ?? []
  } catch {
    return []
  }
}

export async function createContentPost(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  body: { slug?: string; title?: string; body?: string; status?: string }
): Promise<ContentPost | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId) return null
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/posts`, {
      method: "POST",
      headers: contentHeaders(tenantSlug, accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const data = (await res.json()) as { post: ContentPost }
    return data.post ?? null
  } catch {
    return null
  }
}

export async function updateContentPost(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  postId: string,
  body: { slug?: string; title?: string; body?: string; status?: string }
): Promise<ContentPost | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId || !postId) return null
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/posts/${postId}`, {
      method: "PUT",
      headers: contentHeaders(tenantSlug, accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const data = (await res.json()) as { post: ContentPost }
    return data.post ?? null
  } catch {
    return null
  }
}

export async function deleteContentPost(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  postId: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId || !postId) return false
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/posts/${postId}`, {
      method: "DELETE",
      headers: contentHeaders(tenantSlug, accessToken),
    })
    return res.status === 204
  } catch {
    return false
  }
}

export async function fetchContentEvents(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string
): Promise<ContentEvent[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId) return []
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/events`, {
      headers: contentHeaders(tenantSlug, accessToken),
    })
    if (!res.ok) return []
    const data = (await res.json()) as { events: ContentEvent[] }
    return data.events ?? []
  } catch {
    return []
  }
}

export async function createContentEvent(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  body: { title?: string; event_date?: string; venue?: string; location?: string; status?: string }
): Promise<ContentEvent | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId) return null
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/events`, {
      method: "POST",
      headers: contentHeaders(tenantSlug, accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const data = (await res.json()) as { event: ContentEvent }
    return data.event ?? null
  } catch {
    return null
  }
}

export async function updateContentEvent(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  eventId: string,
  body: { title?: string; event_date?: string; venue?: string; location?: string; status?: string }
): Promise<ContentEvent | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId || !eventId) return null
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/events/${eventId}`, {
      method: "PUT",
      headers: contentHeaders(tenantSlug, accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const data = (await res.json()) as { event: ContentEvent }
    return data.event ?? null
  } catch {
    return null
  }
}

export async function deleteContentEvent(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  eventId: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId || !eventId) return false
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/events/${eventId}`, {
      method: "DELETE",
      headers: contentHeaders(tenantSlug, accessToken),
    })
    return res.status === 204
  } catch {
    return false
  }
}

export async function fetchContentMedia(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string
): Promise<ContentMedia[]> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId) return []
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/media`, {
      headers: contentHeaders(tenantSlug, accessToken),
    })
    if (!res.ok) return []
    const data = (await res.json()) as { media: ContentMedia[] }
    return data.media ?? []
  } catch {
    return []
  }
}

export async function createContentMedia(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  body: { s3_key: string; caption?: string; sort_order?: number; status?: string }
): Promise<ContentMedia | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId) return null
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/media`, {
      method: "POST",
      headers: contentHeaders(tenantSlug, accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const data = (await res.json()) as { media: ContentMedia }
    return data.media ?? null
  } catch {
    return null
  }
}

export async function updateContentMedia(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  mediaId: string,
  body: { caption?: string; sort_order?: number; status?: string }
): Promise<ContentMedia | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId || !mediaId) return null
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/media/${mediaId}`, {
      method: "PUT",
      headers: contentHeaders(tenantSlug, accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    const data = (await res.json()) as { media: ContentMedia }
    return data.media ?? null
  } catch {
    return null
  }
}

export async function deleteContentMedia(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  mediaId: string
): Promise<boolean> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId || !mediaId) return false
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/media/${mediaId}`, {
      method: "DELETE",
      headers: contentHeaders(tenantSlug, accessToken),
    })
    return res.status === 204
  } catch {
    return false
  }
}

/** Upload URL for pre-signed POST (Task 1.89). Body: content_length, filename. */
export interface UploadUrlResponse {
  url: string
  method: string
  fields: Record<string, string>
  key: string
}

/** Presigned URL for media display. GET /api/tenant/sites/{id}/media/{id}/url */
export async function fetchMediaPresignedUrl(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  mediaId: string
): Promise<string | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId || !mediaId) return null
  try {
    const res = await fetch(
      `${contentBase(tenantSlug, siteId)}/media/${mediaId}/url`,
      { headers: contentHeaders(tenantSlug, accessToken) }
    )
    if (!res.ok) return null
    const data = (await res.json()) as { url: string }
    return data.url ?? null
  } catch {
    return null
  }
}

export async function fetchUploadUrl(
  tenantSlug: string,
  accessToken: string | null,
  siteId: string,
  body: { content_length: number; filename: string }
): Promise<UploadUrlResponse | null> {
  const base = getApiUrl()
  if (!base || !accessToken || !tenantSlug || !siteId) return null
  try {
    const res = await fetch(`${contentBase(tenantSlug, siteId)}/upload-url`, {
      method: "POST",
      headers: contentHeaders(tenantSlug, accessToken),
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    return (await res.json()) as UploadUrlResponse
  } catch {
    return null
  }
}
