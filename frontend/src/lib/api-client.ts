/**
 * ApiClient — the single HTTP transport for the 9host backend (SPEC Module 5).
 *
 * - Token selection is explicit by auth mode and never crosses over:
 *     "tuser"   → localStorage["9host_site_token"] (site-login JWT) only
 *     "cognito" → Amplify session access token, cached in localStorage["9host_cognito_token"]
 * - Tenant scope (X-Tenant-Slug) and superadmin impersonation (X-Impersonate-Tenant)
 *   are bound to a client instance via `apiClient.forTenant(slug, { impersonate })`
 *   and attached per request. There is no module-level impersonation state.
 */

export const COGNITO_TOKEN_KEY = "9host_cognito_token"
export const SITE_TOKEN_KEY = "9host_site_token"
/** Pre-T-10 key for the site-login JWT; migrated to SITE_TOKEN_KEY on first read. */
const LEGACY_SITE_TOKEN_KEY = "9host-site-token"

export type AuthMode = "cognito" | "tuser"

function storageGet(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function storageSet(key: string, value: string | null): void {
  try {
    if (value) localStorage.setItem(key, value)
    else localStorage.removeItem(key)
  } catch {
    // storage unavailable — ignore
  }
}

/** Site-login (TUSER) JWT. Migrates the legacy "9host-site-token" key once. */
export function readSiteToken(): string | null {
  const token = storageGet(SITE_TOKEN_KEY)
  if (token) return token
  const legacy = storageGet(LEGACY_SITE_TOKEN_KEY)
  if (!legacy) return null
  storageSet(SITE_TOKEN_KEY, legacy)
  storageSet(LEGACY_SITE_TOKEN_KEY, null)
  return legacy
}

export function writeSiteToken(token: string | null): void {
  storageSet(SITE_TOKEN_KEY, token)
  storageSet(LEGACY_SITE_TOKEN_KEY, null)
}

/** A site-login session (TUSER) is active iff a site token is stored; otherwise Cognito. */
export function getAuthMode(): AuthMode {
  return readSiteToken() ? "tuser" : "cognito"
}

async function readCognitoToken(): Promise<string | null> {
  try {
    const { fetchAuthSession } = await import("aws-amplify/auth")
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    storageSet(COGNITO_TOKEN_KEY, token)
    return token
  } catch {
    return storageGet(COGNITO_TOKEN_KEY)
  }
}

/** Bearer token for the given (default: active) auth mode. Never falls through to the other mode. */
export async function getToken(mode: AuthMode = getAuthMode()): Promise<string | null> {
  return mode === "tuser" ? readSiteToken() : readCognitoToken()
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  body?: unknown
  /**
   * Explicit bearer token. `undefined` → token for the active auth mode;
   * `null` → caller is unauthenticated, the request is not sent.
   */
  token?: string | null
  /** Public endpoint: send without Authorization. */
  anonymous?: boolean
}

export type ApiResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; status: number; error: string; code?: string }

export interface Transport {
  request<T>(path: string, opts?: RequestOptions): Promise<ApiResult<T>>
}

export interface TenantApi extends Transport {
  readonly tenantSlug: string
  readonly impersonate: boolean
}

export interface ApiClient extends Transport {
  forTenant(tenantSlug: string, opts?: { impersonate?: boolean }): TenantApi
}

function apiBase(): string {
  const url = import.meta.env.VITE_API_URL as string | undefined
  return url ? url.replace(/\/$/, "") : ""
}

async function send<T>(
  path: string,
  opts: RequestOptions,
  scopeHeaders: Record<string, string>
): Promise<ApiResult<T>> {
  const base = apiBase()
  if (!base) return { ok: false, status: 0, error: "API not configured" }

  const headers: Record<string, string> = { ...scopeHeaders }
  if (!opts.anonymous) {
    const token = opts.token === undefined ? await getToken() : opts.token
    if (!token) return { ok: false, status: 401, error: "Not authenticated" }
    headers.Authorization = `Bearer ${token}`
  }
  if (opts.body !== undefined) headers["Content-Type"] = "application/json"

  let res: Response
  try {
    res = await fetch(`${base}${path}`, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    })
  } catch {
    return { ok: false, status: 0, error: "Network error" }
  }

  let data: unknown
  try {
    const text = await res.text()
    data = text ? JSON.parse(text) : undefined
  } catch {
    data = undefined
  }
  if (res.ok) return { ok: true, status: res.status, data: data as T }
  const err = (data ?? {}) as { error?: string; code?: string }
  return {
    ok: false,
    status: res.status,
    error: err.error || `Request failed (${res.status})`,
    code: err.code,
  }
}

export const apiClient: ApiClient = {
  request: (path, opts = {}) => send(path, opts, {}),
  forTenant(tenantSlug, { impersonate = false } = {}) {
    const slug = tenantSlug.trim().toLowerCase()
    const scopeHeaders: Record<string, string> = { "X-Tenant-Slug": slug }
    if (impersonate) scopeHeaders["X-Impersonate-Tenant"] = slug
    return {
      tenantSlug: slug,
      impersonate,
      request: (path, opts = {}) => send(path, opts, scopeHeaders),
    }
  },
}
