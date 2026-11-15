/**
 * T-31e: block editor Preview (save if needed -> draft-publish -> draft-token -> new tab)
 * and the `_home` starter doc (ADR-0003 §6, owner answer 2).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import type { ComponentType } from "react"

vi.hoisted(() => {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
})

vi.mock("aws-amplify/auth", async (orig) => ({
  ...(await orig<object>()),
  fetchAuthSession: async () => ({ tokens: { accessToken: { toString: () => "cognito-jwt" } } }),
}))
vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ isAuthenticated: true, loading: false, isSiteUser: false, userDisplay: null }),
}))
vi.mock("@/hooks/use-admin-tenants", () => ({
  useAdminTenants: () => ({ isSuperadmin: false, loading: false, tenants: [], error: null, refetch: vi.fn() }),
}))
vi.mock("@/hooks/use-tenants", () => ({
  useTenants: () => ({ tenants: [], loading: false, refetch: vi.fn() }),
}))
// Puck stub: the loaded block types plus our header actions.
vi.mock("@puckeditor/core", () => ({
  Puck: ({ data, overrides }: { data: { content: { type: string }[] }; overrides: { headerActions: ComponentType } }) => {
    const Actions = overrides.headerActions
    return (
      <div>
        <div data-testid="puck">{data.content.map((b) => b.type).join(",")}</div>
        <Actions />
      </div>
    )
  },
}))

import App from "@/App"

const PREVIEW_URL = "https://acme.echo9.net/preview/?token=t"
const fetchMock = vi.fn()

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }))
}
const calls = () => fetchMock.mock.calls.map(([u, init]) => `${init?.method ?? "GET"} ${new URL(u).pathname}`)

beforeEach(() => {
  const site = { id: "s1", name: "Acme", slug: "acme", status: "draft", editor: "blocks", template_id: "business-generic" }
  fetchMock.mockReset()
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    const path = new URL(url).pathname
    if (path === "/api/tenant/sites") return json({ sites: [site] })
    if (path === "/api/tenant/sites/s1/pages/about")
      return json({ page: { path: "about", title: "About", body: "<p>Old</p>", status: "DRAFT" } })
    if (path === "/api/tenant/sites/s1/pages/_home") return json({ error: "Page not found" }, 404)
    if (path === "/api/tenant/sites/s1/pages" && init?.method === "POST")
      return json({ page: { path: "_home", status: "DRAFT" } }, 201)
    if (path === "/api/tenant/sites/s1/draft-publish") return json({ draft: { files_count: 3 } })
    if (path === "/api/tenant/sites/s1/draft-token") return json({ token: "t", preview_url: PREVIEW_URL, expires_in: 900 })
    if (path.match(/\/api\/tenant\/sites\/s1\/(pages|posts|events|media)$/))
      return json({ pages: [{ path: "_home" }, { path: "about", title: "About" }], posts: [], events: [], media: [] })
    return json({})
  })
  vi.stubGlobal("fetch", fetchMock)
  vi.stubEnv("VITE_API_URL", "https://api.test")
  vi.stubEnv("VITE_ENABLE_BLOCK_EDITOR", "true")
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

function openEditor(pagePath: string) {
  window.history.pushState({}, "", `/acme/sites/s1/pages/${pagePath}/edit`)
  return render(<App />)
}

describe("block editor Preview", () => {
  it("opens a tab on click, then draft-publishes and points it at the preview URL", async () => {
    const tab = { opener: {}, close: vi.fn(), location: { href: "" } }
    const open = vi.fn(() => tab)
    vi.stubGlobal("open", open)
    openEditor("about")
    await screen.findByTestId("puck")
    fireEvent.click(screen.getByRole("button", { name: /Preview/ }))
    await waitFor(() => expect(tab.location.href).toBe(PREVIEW_URL))
    expect(open).toHaveBeenCalledWith("", "_blank")
    expect(tab.opener).toBeNull()
    // Saved and clean: no save before the draft build.
    const c = calls()
    expect(c.filter((x) => x.includes("/pages/about") && !x.startsWith("GET"))).toEqual([])
    expect(c.indexOf("POST /api/tenant/sites/s1/draft-publish")).toBeLessThan(c.indexOf("GET /api/tenant/sites/s1/draft-token"))
  })

  it("new _home: starts from a Hero, saves (POST _home) before previewing, shows a link when popups are blocked", async () => {
    vi.stubGlobal("open", vi.fn(() => null))
    openEditor("_home")
    expect((await screen.findByTestId("puck")).textContent).toBe("Hero")
    fireEvent.click(screen.getByRole("button", { name: /Preview/ }))
    const link = await screen.findByRole("link", { name: "Open preview" })
    expect(link.getAttribute("href")).toBe(PREVIEW_URL)
    const post = fetchMock.mock.calls.find(([u, init]) => init?.method === "POST" && new URL(u).pathname.endsWith("/pages"))
    const body = JSON.parse(String(post?.[1]?.body))
    expect(body.path).toBe("_home")
    expect(body.doc.content[0]).toMatchObject({ type: "Hero", props: { heading: "Acme" } })
    const c = calls()
    expect(c.indexOf("POST /api/tenant/sites/s1/pages")).toBeLessThan(c.indexOf("POST /api/tenant/sites/s1/draft-publish"))
  })
})
