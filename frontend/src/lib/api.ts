/**
 * Compatibility layer over `apiClient` (lib/api-client.ts).
 *
 * Tenant-scoped functions take a `TenantApi` (from `useTenantScope().api`), which
 * carries X-Tenant-Slug and, only for superadmin impersonation, X-Impersonate-Tenant.
 * Platform/admin functions use the unscoped `apiClient`.
 */

import {
  apiClient,
  readSiteToken,
  writeSiteToken,
  type RequestOptions,
  type TenantApi,
  type Transport,
} from "@/lib/api-client"

export {
  apiClient,
  getToken,
  getAuthMode,
  SITE_TOKEN_KEY,
  COGNITO_TOKEN_KEY,
  type ApiResult,
  type AuthMode,
  type TenantApi,
} from "@/lib/api-client"

/** Data on success, null on any failure. `token: null` short-circuits without a request. */
async function call<T>(
  t: Transport,
  path: string,
  token: string | null,
  opts: Omit<RequestOptions, "token"> = {}
): Promise<T | null> {
  const r = await t.request<T>(path, { ...opts, token })
  return r.ok ? (r.data ?? null) : null
}

/** True when the request succeeded (used for DELETE/PUT without a body we care about). */
async function succeeded(
  t: Transport,
  path: string,
  token: string | null,
  opts: Omit<RequestOptions, "token"> = {}
): Promise<boolean> {
  return (await t.request(path, { ...opts, token })).ok
}

/** Call that surfaces the backend `error` message by throwing. */
async function callOrThrow<T>(
  t: Transport,
  path: string,
  token: string | null,
  opts: Omit<RequestOptions, "token"> = {}
): Promise<T> {
  const r = await t.request<T>(path, { ...opts, token })
  if (!r.ok) throw new Error(r.error)
  return r.data
}

const enc = encodeURIComponent

// -----------------------------------------------------------------------------
// Auth (site login / TUSER)
// -----------------------------------------------------------------------------

/** Storage key for site user display (username or display_name). */
export const SITE_USER_DISPLAY_KEY = "9host-site-user-display"

/** Site login response from POST /api/auth/site-login */
export interface SiteLoginResponse {
  token: string
  tenant_slug: string
  role: string
  username?: string
  display_name?: string
}

/** Check if user is authenticated via site login (non-Cognito). */
export function isSiteUser(): boolean {
  return !!readSiteToken()
}

/** Store the site-login session (switches auth mode to TUSER). */
export function setSiteSession(token: string, display: string | null): void {
  writeSiteToken(token)
  try {
    if (display) localStorage.setItem(SITE_USER_DISPLAY_KEY, display)
  } catch {
    // ignore
  }
}

/** Clear site token and user display (call on sign out for site users, and on Cognito sign-in). */
export function clearSiteToken(): void {
  writeSiteToken(null)
  try {
    localStorage.removeItem(SITE_USER_DISPLAY_KEY)
  } catch {
    // ignore
  }
}

/** Get site user display string (display_name or username). Returns null if not a site user. */
export function getSiteUserDisplay(): string | null {
  if (!isSiteUser()) return null
  try {
    return localStorage.getItem(SITE_USER_DISPLAY_KEY)
  } catch {
    return null
  }
}

export type SiteLoginResult =
  | { ok: true; data: SiteLoginResponse }
  | { ok: false; error: string; status?: number }

/** Site login — authenticate non-Cognito tenant user. status 503 = service unavailable. */
export async function siteLogin(
  body: { username: string; password: string; site: string }
): Promise<SiteLoginResult> {
  const r = await apiClient.request<SiteLoginResponse>("/api/auth/site-login", {
    method: "POST",
    body,
    anonymous: true,
  })
  if (r.ok) return { ok: true, data: r.data }
  if (r.status === 0) return { ok: false, error: r.error, status: 0 }
  if (r.status === 503) return { ok: false, error: "Service unavailable", status: 503 }
  return { ok: false, error: "Invalid username, password, or site", status: r.status }
}

// -----------------------------------------------------------------------------
// Platform / superadmin
// -----------------------------------------------------------------------------

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

/** GET /api/admin/edge-kvs — live CloudFront KVS routing + custom domain health (superadmin). */
export interface EdgeKvsEntry {
  hostname: string
  tenant: string
  site_id: string
}

export interface EdgeDomainHealth {
  domain: string
  tenant_slug: string
  site_id: string
  status: string
  cf_status?: string | null
  ssl_status?: string | null
}

export interface EdgeKvsResponse {
  entries: EdgeKvsEntry[]
  domains: EdgeDomainHealth[]
}

export const fetchAdminUsers = (accessToken: string | null) =>
  call<AdminUsersResponse>(apiClient, "/api/admin/users", accessToken)

export const fetchAdminStats = (accessToken: string | null) =>
  call<AdminStats>(apiClient, "/api/admin/stats", accessToken)

/** Fetch all tenants (superadmin only). Any failure (incl. 403) → not superadmin. */
export async function fetchAllTenants(
  accessToken: string | null
): Promise<FetchAllTenantsResult> {
  const data = await call<AdminTenantsResponse>(apiClient, "/api/admin/tenants", accessToken)
  return data ? { tenants: data.tenants ?? [], isSuperadmin: true } : { tenants: [], isSuperadmin: false }
}

/** Superadmin-only edge routing table + domains health. Returns the error message on failure. */
export async function fetchEdgeKvs(
  accessToken: string | null
): Promise<{ ok: true; data: EdgeKvsResponse } | { ok: false; error: string }> {
  const r = await apiClient.request<EdgeKvsResponse>("/api/admin/edge-kvs", { token: accessToken })
  if (!r.ok) return { ok: false, error: r.error }
  return { ok: true, data: { entries: r.data?.entries ?? [], domains: r.data?.domains ?? [] } }
}

/** Create tenant (superadmin only). Body: slug (max 60 chars), name, tier. */
export const createAdminTenant = (
  accessToken: string | null,
  body: { slug: string; name: string; tier?: string }
) => call<AdminTenantDetail>(apiClient, "/api/admin/tenants", accessToken, { method: "POST", body })

export const fetchAdminTenant = (accessToken: string | null, slug: string) =>
  call<AdminTenantDetail>(apiClient, `/api/admin/tenants/${enc(slug)}`, accessToken)

/** DELETE tenant (superadmin only). Cascade-deletes all sub-resources. */
export const deleteAdminTenant = (accessToken: string | null, slug: string) =>
  succeeded(apiClient, `/api/admin/tenants/${enc(slug)}`, accessToken, { method: "DELETE" })

/** Admin settings: update tenant tier, name, module_overrides, owner_sub */
export const putAdminTenantSettings = (
  accessToken: string | null,
  tenantSlug: string,
  body: {
    tier?: string
    name?: string
    module_overrides?: Record<string, boolean>
    owner_sub?: string | null
  }
) =>
  call<AdminTenantDetail>(apiClient, `/api/admin/tenants/${enc(tenantSlug)}/settings`, accessToken, {
    method: "PUT",
    body,
  })

// -----------------------------------------------------------------------------
// Tenants for the current user
// -----------------------------------------------------------------------------

/** Self-serve tenant creation response (Task 4.1) */
export interface CreateTenantResponse {
  slug: string
  name: string
  tier: string
  owner_sub?: string
  created_at?: string
  updated_at?: string
}

export async function fetchTenants(accessToken: string | null): Promise<Tenant[]> {
  return (await call<TenantsResponse>(apiClient, "/api/tenants", accessToken))?.tenants ?? []
}

/** Create tenant (self-serve, Cognito, tier FREE) with error details. */
export async function createTenantWithError(
  accessToken: string | null,
  body: { slug: string; name?: string }
): Promise<{ ok: true; data: CreateTenantResponse } | { ok: false; error: string; status?: number }> {
  const r = await apiClient.request<CreateTenantResponse>("/api/tenants", {
    method: "POST",
    body,
    token: accessToken,
  })
  return r.ok ? { ok: true, data: r.data } : { ok: false, error: r.error, status: r.status }
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

export const fetchTenant = (api: TenantApi, accessToken: string | null) =>
  call<TenantMetadata>(api, "/api/tenant", accessToken)

/** PATCH tenant module_overrides (admin/manager only). Task 2.22. */
export const patchTenantModuleOverrides = (
  api: TenantApi,
  accessToken: string | null,
  module_overrides: Record<string, boolean>
) => call<TenantMetadata>(api, "/api/tenant", accessToken, { method: "PATCH", body: { module_overrides } })

/** Transfer tenant owner. Requires current user to be owner. */
export async function putTransferOwner(
  api: TenantApi,
  accessToken: string | null,
  newOwnerSub: string
): Promise<boolean> {
  if (!newOwnerSub) return false
  return succeeded(api, "/api/tenant", accessToken, { method: "PUT", body: { owner_sub: newOwnerSub } })
}

// -----------------------------------------------------------------------------
// Tenant users, TUSERs, roles
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

export async function fetchTenantUsers(api: TenantApi, accessToken: string | null): Promise<TenantUser[]> {
  return (await call<TenantUsersResponse>(api, "/api/tenant/users", accessToken))?.users ?? []
}

export async function fetchUserPermissions(
  api: TenantApi,
  accessToken: string | null,
  userSub: string
): Promise<ModulePermissions | null> {
  const path = `/api/tenant/users/${enc(userSub)}/permissions`
  return (await call<{ permissions: ModulePermissions }>(api, path, accessToken))?.permissions ?? null
}

export async function updateUserPermissions(
  api: TenantApi,
  accessToken: string | null,
  userSub: string,
  permissions: Partial<ModulePermissions>
): Promise<ModulePermissions | null> {
  const path = `/api/tenant/users/${enc(userSub)}/permissions`
  const data = await call<{ permissions: ModulePermissions }>(api, path, accessToken, {
    method: "PUT",
    body: { permissions },
  })
  return data?.permissions ?? null
}

export async function fetchTenantTUsers(api: TenantApi, accessToken: string | null): Promise<TenantTUser[]> {
  return (await call<{ users: TenantTUser[] }>(api, "/api/tenant/tusers", accessToken))?.users ?? []
}

export async function createTenantTUser(
  api: TenantApi,
  accessToken: string | null,
  body: { username: string; password: string; display_name?: string; role: string }
): Promise<TenantTUser | null> {
  const data = await call<{ user: TenantTUser }>(api, "/api/tenant/tusers", accessToken, { method: "POST", body })
  return data?.user ?? null
}

export async function updateTenantTUser(
  api: TenantApi,
  accessToken: string | null,
  username: string,
  body: { role?: string; display_name?: string; password?: string }
): Promise<TenantTUser | null> {
  const data = await call<{ user: TenantTUser }>(api, `/api/tenant/tusers/${enc(username)}`, accessToken, {
    method: "PUT",
    body,
  })
  return data?.user ?? null
}

export const deleteTenantTUser = (api: TenantApi, accessToken: string | null, username: string) =>
  succeeded(api, `/api/tenant/tusers/${enc(username)}`, accessToken, { method: "DELETE" })

export async function fetchTenantRoles(api: TenantApi, accessToken: string | null): Promise<TenantRole[]> {
  return (await call<{ roles: TenantRole[] }>(api, "/api/tenant/roles", accessToken))?.roles ?? []
}

export async function createTenantRole(
  api: TenantApi,
  accessToken: string | null,
  body: { name: string; permissions: Record<string, boolean> }
): Promise<TenantRole | null> {
  const data = await call<{ role: TenantRole }>(api, "/api/tenant/roles", accessToken, { method: "POST", body })
  return data?.role ?? null
}

export async function updateTenantRole(
  api: TenantApi,
  accessToken: string | null,
  roleName: string,
  body: { permissions: Record<string, boolean> }
): Promise<TenantRole | null> {
  const data = await call<{ role: TenantRole }>(api, `/api/tenant/roles/${enc(roleName)}`, accessToken, {
    method: "PUT",
    body,
  })
  return data?.role ?? null
}

/** Delete custom role (admin/manager only). Fails if users are assigned. */
export const deleteTenantRole = (api: TenantApi, accessToken: string | null, roleName: string) =>
  succeeded(api, `/api/tenant/roles/${enc(roleName)}`, accessToken, { method: "DELETE" })

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

export const fetchAnalytics = (api: TenantApi, accessToken: string | null) =>
  call<AnalyticsResponse>(api, "/api/tenant/analytics", accessToken)

// -----------------------------------------------------------------------------
// Sites
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
  published_at?: string | null
  published_version?: number | null
  created_at: string
  updated_at: string
}

export interface SitesResponse {
  sites: Site[]
}

export interface SiteResponse {
  site: Site
}

export async function fetchSites(api: TenantApi, accessToken: string | null): Promise<Site[]> {
  return (await call<SitesResponse>(api, "/api/tenant/sites", accessToken))?.sites ?? []
}

export async function createSite(
  api: TenantApi,
  accessToken: string | null,
  body: { name: string; slug?: string; status?: string; template_id?: string | null }
): Promise<Site | null> {
  const payload = { ...body }
  if (payload.template_id === null) delete payload.template_id
  const data = await call<SiteResponse>(api, "/api/tenant/sites", accessToken, { method: "POST", body: payload })
  return data?.site ?? null
}

export async function updateSite(
  api: TenantApi,
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
  const data = await call<SiteResponse>(api, `/api/tenant/sites/${enc(siteId)}`, accessToken, {
    method: "PUT",
    body,
  })
  return data?.site ?? null
}

export const deleteSite = (api: TenantApi, accessToken: string | null, siteId: string) =>
  succeeded(api, `/api/tenant/sites/${enc(siteId)}`, accessToken, { method: "DELETE" })

/** GET /api/validate-slug?slug={slug}&exclude_site_id={id} (Task 1.77). */
export interface ValidateSlugResponse {
  available: boolean
  slug: string
}

export async function validateSlug(
  api: TenantApi,
  accessToken: string | null,
  slug: string,
  excludeSiteId?: string | null
): Promise<ValidateSlugResponse | null> {
  if (!slug?.trim()) return null
  const params = new URLSearchParams({ slug: slug.trim().toLowerCase() })
  if (excludeSiteId) params.set("exclude_site_id", excludeSiteId)
  return call<ValidateSlugResponse>(api, `/api/validate-slug?${params}`, accessToken)
}

/** Site preview (Task 1.79). GET /api/tenant/sites/{id}/preview?template={slug} */
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
  api: TenantApi,
  accessToken: string | null,
  siteId: string,
  templateSlug?: string | null
): Promise<SitePreviewData | null> {
  const qs = templateSlug ? `?${new URLSearchParams({ template: templateSlug })}` : ""
  const path = `/api/tenant/sites/${enc(siteId)}/preview${qs}`
  return (await call<{ preview: SitePreviewData }>(api, path, accessToken))?.preview ?? null
}

/** Draft preview token response (Task 1.117). */
export interface DraftTokenResponse {
  token: string
  preview_url: string
  expires_in: number
}

/** Draft preview token; call fetchDraftPublish first so the preview is current. */
export const fetchDraftToken = (api: TenantApi, accessToken: string | null, siteId: string) =>
  call<DraftTokenResponse>(api, `/api/tenant/sites/${enc(siteId)}/draft-token`, accessToken)

/** Render current content to the draft/ prefix. */
export async function fetchDraftPublish(
  api: TenantApi,
  accessToken: string | null,
  siteId: string
): Promise<{ files_count: number } | null> {
  const path = `/api/tenant/sites/${enc(siteId)}/draft-publish`
  const data = await call<{ draft: { files_count: number } }>(api, path, accessToken, { method: "POST" })
  return data?.draft ?? null
}

/** Publish site (Task 1.96). Admin/manager only. Throws with the backend error message. */
export async function publishSite(
  api: TenantApi,
  accessToken: string | null,
  siteId: string
): Promise<{ version: number; published_at: string; files_count: number; is_default: boolean } | null> {
  const data = await callOrThrow<{
    publish: { version: number; published_at: string; files_count: number; is_default: boolean }
  }>(api, `/api/tenant/sites/${enc(siteId)}/publish`, accessToken, { method: "POST" })
  return data?.publish ?? null
}

// -----------------------------------------------------------------------------
// Custom domains — Cloudflare for SaaS (Pro+ tier)
// -----------------------------------------------------------------------------

/** DNS record the tenant must add for Cloudflare hostname ownership / SSL validation. */
export interface DomainValidationRecord {
  type: "TXT"
  name: string
  value: string
  purpose: "ownership" | "ssl"
}

export type DomainStatus = "PENDING_VALIDATION" | "ACTIVE"

export interface Domain {
  domain: string
  site_id: string
  status: DomainStatus
  /** Always "proxy.echo9.net" */
  cname_target?: string
  cf_hostname_id?: string
  cf_status?: string
  ssl_status?: string
  validation_records?: DomainValidationRecord[]
  verification_errors?: string[]
  /** Always "proxy.echo9.net" (kept by the backend for compatibility) */
  verification_cname_target?: string
  created_at?: string
  updated_at?: string
}

export interface DomainsResponse {
  domains: Domain[]
}

export interface ActivateDomainResponse {
  domain: Domain
  validation_records: DomainValidationRecord[]
  message: string
}

export async function fetchDomains(api: TenantApi, accessToken: string | null): Promise<Domain[]> {
  return (await call<DomainsResponse>(api, "/api/tenant/domains", accessToken))?.domains ?? []
}

/** Add a custom domain (201 {domain, message}). Throws with the backend `error` on failure. */
export async function createDomain(
  api: TenantApi,
  accessToken: string | null,
  body: { domain: string; site_id: string }
): Promise<Domain> {
  const data = await callOrThrow<{ domain: Domain; message?: string }>(api, "/api/tenant/domains", accessToken, {
    method: "POST",
    body,
  })
  return data.domain
}

export const deleteDomain = (api: TenantApi, accessToken: string | null, domain: string) =>
  succeeded(api, `/api/tenant/domains/${enc(domain)}`, accessToken, { method: "DELETE" })

/** Re-check Cloudflare hostname status. Throws with the backend `error` on failure. */
export const activateDomain = (api: TenantApi, accessToken: string | null, domain: string) =>
  callOrThrow<ActivateDomainResponse>(api, `/api/tenant/domains/${enc(domain)}/activate`, accessToken, {
    method: "POST",
  })

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

export async function createBillingCheckout(
  api: TenantApi,
  accessToken: string | null,
  body: { tier: "pro" | "business"; success_url: string; cancel_url: string }
): Promise<BillingCheckoutResult> {
  const r = await api.request<BillingCheckoutResponse>("/api/tenant/billing/checkout", {
    method: "POST",
    body,
    token: accessToken,
  })
  if (r.ok && r.data?.url) return { ok: true, url: r.data.url, session_id: r.data.session_id }
  return { ok: false, error: r.ok ? "Failed to start checkout." : r.error }
}

export type BillingPortalResult =
  | { ok: true; url: string }
  | { ok: false; error: string }

export async function createBillingPortal(
  api: TenantApi,
  accessToken: string | null,
  body: { return_url: string }
): Promise<BillingPortalResult> {
  const r = await api.request<BillingPortalResponse>("/api/tenant/billing/portal", {
    method: "POST",
    body,
    token: accessToken,
  })
  if (r.ok && r.data?.url) return { ok: true, url: r.data.url }
  return { ok: false, error: r.ok ? "Failed to open billing portal." : r.error }
}

// -----------------------------------------------------------------------------
// Templates
// -----------------------------------------------------------------------------

export interface Template {
  slug: string
  name: string
  description: string
  tier_required: string
  components: Record<string, unknown>
  created_at?: string
  updated_at?: string
  /** Task 1.124: true if tenant-owned forked template */
  is_custom?: boolean
  /** Task 1.124: original platform template slug when forked */
  forked_from?: string
}

export interface TemplatesResponse {
  templates: Template[]
}

export async function fetchTemplates(api: TenantApi, accessToken: string | null): Promise<Template[]> {
  return (await call<TemplatesResponse>(api, "/api/templates", accessToken))?.templates ?? []
}

/** Fork a platform template (Task 1.123). Pro+ only. */
export async function forkTemplate(
  api: TenantApi,
  accessToken: string | null,
  body: { template_slug: string; name?: string; slug?: string }
): Promise<{ slug: string; name: string } | null> {
  const data = await call<{ template: { slug: string; name: string } }>(
    api,
    "/api/tenant/templates/fork",
    accessToken,
    { method: "POST", body }
  )
  return data?.template ?? null
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

export async function fetchAdminTemplates(accessToken: string | null): Promise<AdminTemplate[]> {
  return (await call<AdminTemplatesResponse>(apiClient, "/api/admin/templates", accessToken))?.templates ?? []
}

export type CreateAdminTemplateResult =
  | { success: true; template: AdminTemplate }
  | { success: false; error: string }

export async function createAdminTemplate(
  accessToken: string | null,
  body: { slug: string; name: string; description?: string; tier_required?: string; components?: Record<string, unknown> }
): Promise<CreateAdminTemplateResult> {
  const r = await apiClient.request<AdminTemplate>("/api/admin/templates", {
    method: "POST",
    body,
    token: accessToken,
  })
  return r.ok ? { success: true, template: r.data } : { success: false, error: r.error }
}

export const updateAdminTemplate = (
  accessToken: string | null,
  slug: string,
  body: { name?: string; description?: string; tier_required?: string; components?: Record<string, unknown> }
) => call<AdminTemplate>(apiClient, `/api/admin/templates/${enc(slug)}`, accessToken, { method: "PUT", body })

export const deleteAdminTemplate = (accessToken: string | null, slug: string) =>
  succeeded(apiClient, `/api/admin/templates/${enc(slug)}`, accessToken, { method: "DELETE" })

// -----------------------------------------------------------------------------
// Content API (pages, posts, events, media) — Task 1.95
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

const contentPath = (siteId: string, rest: string) => `/api/tenant/sites/${enc(siteId)}/${rest}`

// --- Pages ---

export async function fetchContentPages(api: TenantApi, accessToken: string | null, siteId: string): Promise<ContentPage[]> {
  return (await call<{ pages: ContentPage[] }>(api, contentPath(siteId, "pages"), accessToken))?.pages ?? []
}

export async function createContentPage(
  api: TenantApi,
  accessToken: string | null,
  siteId: string,
  body: { path: string; title: string; body?: string; status?: string }
): Promise<ContentPage | null> {
  const data = await call<{ page: ContentPage }>(api, contentPath(siteId, "pages"), accessToken, { method: "POST", body })
  return data?.page ?? null
}

export async function updateContentPage(
  api: TenantApi,
  accessToken: string | null,
  siteId: string,
  pagePath: string,
  body: { title?: string; body?: string; status?: string }
): Promise<ContentPage | null> {
  const path = contentPath(siteId, `pages/${enc(pagePath)}`)
  return (await call<{ page: ContentPage }>(api, path, accessToken, { method: "PUT", body }))?.page ?? null
}

export const deleteContentPage = (api: TenantApi, accessToken: string | null, siteId: string, pagePath: string) =>
  succeeded(api, contentPath(siteId, `pages/${enc(pagePath)}`), accessToken, { method: "DELETE" })

// --- Posts ---

export async function fetchContentPosts(api: TenantApi, accessToken: string | null, siteId: string): Promise<ContentPost[]> {
  return (await call<{ posts: ContentPost[] }>(api, contentPath(siteId, "posts"), accessToken))?.posts ?? []
}

export async function createContentPost(
  api: TenantApi,
  accessToken: string | null,
  siteId: string,
  body: { slug?: string; title?: string; body?: string; status?: string }
): Promise<ContentPost | null> {
  const data = await call<{ post: ContentPost }>(api, contentPath(siteId, "posts"), accessToken, { method: "POST", body })
  return data?.post ?? null
}

export async function updateContentPost(
  api: TenantApi,
  accessToken: string | null,
  siteId: string,
  postId: string,
  body: { slug?: string; title?: string; body?: string; status?: string }
): Promise<ContentPost | null> {
  const path = contentPath(siteId, `posts/${enc(postId)}`)
  return (await call<{ post: ContentPost }>(api, path, accessToken, { method: "PUT", body }))?.post ?? null
}

export const deleteContentPost = (api: TenantApi, accessToken: string | null, siteId: string, postId: string) =>
  succeeded(api, contentPath(siteId, `posts/${enc(postId)}`), accessToken, { method: "DELETE" })

// --- Events ---

export async function fetchContentEvents(api: TenantApi, accessToken: string | null, siteId: string): Promise<ContentEvent[]> {
  return (await call<{ events: ContentEvent[] }>(api, contentPath(siteId, "events"), accessToken))?.events ?? []
}

export async function createContentEvent(
  api: TenantApi,
  accessToken: string | null,
  siteId: string,
  body: { title?: string; event_date?: string; venue?: string; location?: string; status?: string }
): Promise<ContentEvent | null> {
  const data = await call<{ event: ContentEvent }>(api, contentPath(siteId, "events"), accessToken, { method: "POST", body })
  return data?.event ?? null
}

export async function updateContentEvent(
  api: TenantApi,
  accessToken: string | null,
  siteId: string,
  eventId: string,
  body: { title?: string; event_date?: string; venue?: string; location?: string; status?: string }
): Promise<ContentEvent | null> {
  const path = contentPath(siteId, `events/${enc(eventId)}`)
  return (await call<{ event: ContentEvent }>(api, path, accessToken, { method: "PUT", body }))?.event ?? null
}

export const deleteContentEvent = (api: TenantApi, accessToken: string | null, siteId: string, eventId: string) =>
  succeeded(api, contentPath(siteId, `events/${enc(eventId)}`), accessToken, { method: "DELETE" })

// --- Media ---

export async function fetchContentMedia(api: TenantApi, accessToken: string | null, siteId: string): Promise<ContentMedia[]> {
  return (await call<{ media: ContentMedia[] }>(api, contentPath(siteId, "media"), accessToken))?.media ?? []
}

export async function createContentMedia(
  api: TenantApi,
  accessToken: string | null,
  siteId: string,
  body: { s3_key: string; caption?: string; sort_order?: number; status?: string }
): Promise<ContentMedia | null> {
  const data = await call<{ media: ContentMedia }>(api, contentPath(siteId, "media"), accessToken, { method: "POST", body })
  return data?.media ?? null
}

export async function updateContentMedia(
  api: TenantApi,
  accessToken: string | null,
  siteId: string,
  mediaId: string,
  body: { caption?: string; sort_order?: number; status?: string }
): Promise<ContentMedia | null> {
  const path = contentPath(siteId, `media/${enc(mediaId)}`)
  return (await call<{ media: ContentMedia }>(api, path, accessToken, { method: "PUT", body }))?.media ?? null
}

export const deleteContentMedia = (api: TenantApi, accessToken: string | null, siteId: string, mediaId: string) =>
  succeeded(api, contentPath(siteId, `media/${enc(mediaId)}`), accessToken, { method: "DELETE" })

/** Presigned POST for uploads (Task 1.89). Body: content_length, filename. */
export interface UploadUrlResponse {
  url: string
  method: string
  fields: Record<string, string>
  key: string
}

/** Presigned URL for media display. GET /api/tenant/sites/{id}/media/{id}/url */
export async function fetchMediaPresignedUrl(
  api: TenantApi,
  accessToken: string | null,
  siteId: string,
  mediaId: string
): Promise<string | null> {
  const path = contentPath(siteId, `media/${enc(mediaId)}/url`)
  return (await call<{ url: string }>(api, path, accessToken))?.url ?? null
}

export const fetchUploadUrl = (
  api: TenantApi,
  accessToken: string | null,
  siteId: string,
  body: { content_length: number; filename: string }
) => call<UploadUrlResponse>(api, contentPath(siteId, "upload-url"), accessToken, { method: "POST", body })
