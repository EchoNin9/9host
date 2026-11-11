import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"

const fetchAuthSession = vi.fn()
vi.mock("aws-amplify/auth", () => ({ fetchAuthSession: () => fetchAuthSession() }))

import {
  apiClient,
  getAuthMode,
  getToken,
  COGNITO_TOKEN_KEY,
  SITE_TOKEN_KEY,
} from "@/lib/api-client"

const fetchMock = vi.fn()

function cognitoSession(token: string | null) {
  fetchAuthSession.mockResolvedValue(
    token ? { tokens: { accessToken: { toString: () => token } } } : { tokens: undefined }
  )
}

function okJson(body: unknown = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  })
}

function headersOf(callIndex: number): Record<string, string> {
  return fetchMock.mock.calls[callIndex][1].headers as Record<string, string>
}

beforeEach(() => {
  localStorage.clear()
  fetchAuthSession.mockReset()
  fetchMock.mockReset()
  fetchMock.mockImplementation(async () => okJson())
  vi.stubGlobal("fetch", fetchMock)
  vi.stubEnv("VITE_API_URL", "https://api.test")
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

describe("token selection by auth mode", () => {
  it("TUSER session sends only the site token and never consults Cognito", async () => {
    localStorage.setItem(SITE_TOKEN_KEY, "site-jwt")
    cognitoSession("cognito-jwt")

    expect(getAuthMode()).toBe("tuser")
    await apiClient.request("/api/tenants")

    expect(headersOf(0).Authorization).toBe("Bearer site-jwt")
    expect(fetchAuthSession).not.toHaveBeenCalled()
  })

  it("Cognito session sends the Cognito token and caches it under 9host_cognito_token", async () => {
    cognitoSession("cognito-jwt")

    expect(getAuthMode()).toBe("cognito")
    await apiClient.request("/api/tenants")

    expect(headersOf(0).Authorization).toBe("Bearer cognito-jwt")
    expect(localStorage.getItem(COGNITO_TOKEN_KEY)).toBe("cognito-jwt")
  })

  it("never falls through from one mode to the other", async () => {
    // Cognito mode with no Cognito session must not pick up a site token.
    localStorage.setItem(SITE_TOKEN_KEY, "site-jwt")
    cognitoSession(null)
    expect(await getToken("cognito")).toBeNull()

    // TUSER mode with no site token must not pick up the Cognito token.
    localStorage.clear()
    localStorage.setItem(COGNITO_TOKEN_KEY, "cached-cognito")
    cognitoSession("cognito-jwt")
    expect(await getToken("tuser")).toBeNull()
  })

  it("does not send a request when unauthenticated", async () => {
    cognitoSession(null)
    const r = await apiClient.request("/api/tenants")
    expect(r).toMatchObject({ ok: false, status: 401 })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("migrates the legacy 9host-site-token key", async () => {
    localStorage.setItem("9host-site-token", "legacy-jwt")
    expect(await getToken()).toBe("legacy-jwt")
    expect(localStorage.getItem(SITE_TOKEN_KEY)).toBe("legacy-jwt")
    expect(localStorage.getItem("9host-site-token")).toBeNull()
  })
})

describe("tenant scoping and impersonation headers", () => {
  beforeEach(() => cognitoSession("cognito-jwt"))

  it("unscoped client sends no tenant or impersonation headers", async () => {
    await apiClient.request("/api/admin/tenants")
    expect(headersOf(0)["X-Tenant-Slug"]).toBeUndefined()
    expect(headersOf(0)["X-Impersonate-Tenant"]).toBeUndefined()
  })

  it("non-impersonating scoped client sends X-Tenant-Slug only", async () => {
    await apiClient.forTenant("Acme").request("/api/tenant/sites")
    expect(headersOf(0)["X-Tenant-Slug"]).toBe("acme")
    expect(headersOf(0)["X-Impersonate-Tenant"]).toBeUndefined()
  })

  it("impersonating scoped client sends X-Impersonate-Tenant for its own tenant", async () => {
    await apiClient.forTenant("acme", { impersonate: true }).request("/api/tenant/sites")
    expect(headersOf(0)["X-Tenant-Slug"]).toBe("acme")
    expect(headersOf(0)["X-Impersonate-Tenant"]).toBe("acme")
  })

  it("concurrent scoped clients do not leak headers into each other", async () => {
    // Resolve responses out of order to interleave the two clients' requests.
    let n = 0
    fetchMock.mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve(okJson()), 10 - 3 * n++))
    )
    const admin = apiClient.forTenant("acme", { impersonate: true })
    const tenant = apiClient.forTenant("beta")

    await Promise.all([
      admin.request("/api/tenant/sites"),
      tenant.request("/api/tenant/sites"),
      admin.request("/api/tenant/domains", { method: "POST", body: { domain: "a.com" } }),
      tenant.request("/api/tenant/domains"),
    ])

    const sent = fetchMock.mock.calls.map(([, init]) => init.headers as Record<string, string>)
    const forAcme = sent.filter((h) => h["X-Tenant-Slug"] === "acme")
    const forBeta = sent.filter((h) => h["X-Tenant-Slug"] === "beta")
    expect(forAcme).toHaveLength(2)
    expect(forBeta).toHaveLength(2)
    forAcme.forEach((h) => expect(h["X-Impersonate-Tenant"]).toBe("acme"))
    forBeta.forEach((h) => expect(h["X-Impersonate-Tenant"]).toBeUndefined())

    // A client created later is unaffected by earlier impersonating clients.
    fetchMock.mockImplementation(async () => okJson())
    await apiClient.forTenant("gamma").request("/api/tenant")
    expect(headersOf(4)["X-Impersonate-Tenant"]).toBeUndefined()
  })

  it("surfaces the backend error message and code", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error: "Hostname already exists", code: "cloudflare_conflict" }), {
        status: 409,
      })
    )
    const r = await apiClient.forTenant("acme").request("/api/tenant/domains", { method: "POST", body: {} })
    expect(r).toEqual({ ok: false, status: 409, error: "Hostname already exists", code: "cloudflare_conflict" })
  })
})
