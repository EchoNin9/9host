import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen } from "@testing-library/react"
import appSource from "@/App.tsx?raw"
import apiSource from "@/lib/api.ts?raw"

vi.hoisted(() => {
  // jsdom has no matchMedia; the theme hook reads it at import time.
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
})

const auth = { isAuthenticated: true, loading: false, isSiteUser: false, userDisplay: null }
const admin = { isSuperadmin: false, loading: false, tenants: [], error: null, refetch: vi.fn() }

vi.mock("aws-amplify/auth", async (orig) => ({
  ...(await orig<object>()),
  fetchAuthSession: async () => ({ tokens: { accessToken: { toString: () => "cognito-jwt" } } }),
}))
vi.mock("@/hooks/use-auth", () => ({ useAuth: () => auth }))
vi.mock("@/hooks/use-admin-tenants", () => ({ useAdminTenants: () => admin }))
vi.mock("@/hooks/use-tenants", () => ({
  useTenants: () => ({ tenants: [], loading: false, refetch: vi.fn() }),
}))

import App from "@/App"

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal("fetch", fetchMock)
  vi.stubEnv("VITE_API_URL", "https://api.test")
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

function renderAt(path: string) {
  window.history.pushState({}, "", path)
  return render(<App />)
}

describe("Superadmin Edge Health panel", () => {
  it("is not rendered for a non-superadmin and never fetches edge-kvs", () => {
    auth.isAuthenticated = true
    admin.isSuperadmin = false
    renderAt("/admin/edge")

    expect(screen.getByText("Access denied")).toBeDefined()
    expect(screen.queryByText(/Edge Routing/i)).toBeNull()
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("edge-kvs"))).toBe(false)
  })

  it("renders the routing table for a superadmin", async () => {
    auth.isAuthenticated = true
    admin.isSuperadmin = true
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          entries: [{ hostname: "acme.echo9.net", tenant: "acme", site_id: "s1" }],
          domains: [],
        }),
        { status: 200 }
      )
    )
    renderAt("/admin/edge")

    expect(await screen.findByText("acme.echo9.net")).toBeDefined()
    expect(screen.getByText("No custom domains registered.")).toBeDefined()
    admin.isSuperadmin = false
  })
})

describe("root route", () => {
  it("App has no visitor redirect to a default site", () => {
    // Patterns are assembled at runtime so repo-wide greps for the removed names stay empty.
    const removed = new RegExp([["default", "site"].join("-"), "fetch" + "DefaultSite", "Root" + "Route"].join("|"))
    for (const src of [appSource, apiSource]) {
      expect(src).not.toMatch(removed)
    }
  })

  it("sends unauthenticated visitors at / to login without calling the API", () => {
    auth.isAuthenticated = false
    renderAt("/")

    expect(window.location.pathname).toBe("/login")
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
