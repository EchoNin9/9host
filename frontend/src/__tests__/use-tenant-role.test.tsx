import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"

vi.mock("aws-amplify/auth", () => ({
  fetchAuthSession: () =>
    Promise.resolve({ tokens: { accessToken: { toString: () => "cog" } } }),
}))
vi.mock("@/hooks/use-tenant", () => ({ useTenant: () => ({ tenantSlug: "acme" }) }))
vi.mock("@/context/tenant-scope-context", () => ({
  useTenantScope: () => ({ isSuperadminImpersonating: false }),
}))

import { useTenantRole } from "@/hooks/use-tenant-role"
import { SITE_TOKEN_KEY } from "@/lib/api-client"

const fetchMock = vi.fn()

function jwt(role: string) {
  return `h.${btoa(JSON.stringify({ role }))}.s`
}

beforeEach(() => {
  localStorage.clear()
  fetchMock.mockReset()
  fetchMock.mockResolvedValue(
    new Response(JSON.stringify({ tenants: [{ slug: "acme", role: "manager" }] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    })
  )
  vi.stubGlobal("fetch", fetchMock)
  vi.stubEnv("VITE_API_URL", "https://api.test")
})

const tenantCalls = () =>
  fetchMock.mock.calls.filter((c) => String(c[0]).includes("/api/tenants"))

describe("useTenantRole", () => {
  it("TUSER manager can edit, without calling /api/tenants", async () => {
    localStorage.setItem(SITE_TOKEN_KEY, jwt("manager"))
    const { result } = renderHook(() => useTenantRole())
    await waitFor(() => expect(result.current.role).toBe("manager"))
    expect(result.current.canEdit).toBe(true)
    expect(tenantCalls()).toHaveLength(0)
  })

  it("TUSER member cannot edit", () => {
    localStorage.setItem(SITE_TOKEN_KEY, jwt("member"))
    const { result } = renderHook(() => useTenantRole())
    expect(result.current.canEdit).toBe(false)
    expect(tenantCalls()).toHaveLength(0)
  })

  it("Cognito mode still reads the role from /api/tenants", async () => {
    const { result } = renderHook(() => useTenantRole())
    await waitFor(() => expect(result.current.canEdit).toBe(true))
    expect(result.current.role).toBe("manager")
    expect(tenantCalls().length).toBeGreaterThan(0)
  })
})
