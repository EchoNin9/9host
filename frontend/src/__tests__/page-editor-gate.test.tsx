/**
 * Block editor route gate (ADR-0003 §4, T-31d): the route exists only when
 * VITE_ENABLE_BLOCK_EDITOR === "true", and the editor opens only for sites with
 * editor === "blocks" (otherwise a confirmed "switch" action PATCHes the site).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

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
// Puck itself is not exercised in jsdom: the stub shows what the editor would load.
vi.mock("@puckeditor/core", () => ({
  Puck: ({ data }: { data: { content: { type: string; props: { legacy?: boolean } }[] } }) => (
    <div data-testid="puck">
      {data.content.map((b) => `${b.type}${b.props.legacy ? ":legacy" : ""}`).join(",")}
    </div>
  ),
}))

import App from "@/App"

const fetchMock = vi.fn()
let site: { id: string; name: string; slug: string; status: string; editor: string; template_id: string }

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }))
}

beforeEach(() => {
  site = { id: "s1", name: "Acme", slug: "acme", status: "draft", editor: "richtext", template_id: "business-generic" }
  fetchMock.mockReset()
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    const path = new URL(url).pathname
    if (path === "/api/tenant/sites" ) return json({ sites: [site] })
    if (path === "/api/tenant/sites/s1" && init?.method === "PATCH") {
      site = { ...site, ...JSON.parse(String(init.body)) }
      return json({ site })
    }
    if (path === "/api/tenant/sites/s1/pages/about")
      return json({ page: { path: "about", title: "About", body: "<p>Old</p>", status: "DRAFT" } })
    if (path.match(/\/api\/tenant\/sites\/s1\/(pages|posts|events|media)$/)) return json({ pages: [], posts: [], events: [], media: [] })
    return json({})
  })
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

const EDIT_URL = "/acme/sites/s1/pages/about/edit"

describe("block editor route gate", () => {
  it("is not routed when VITE_ENABLE_BLOCK_EDITOR is off", async () => {
    vi.stubEnv("VITE_ENABLE_BLOCK_EDITOR", "false")
    renderAt(EDIT_URL)
    await waitFor(() => expect(window.location.pathname).toBe("/"))
    expect(screen.queryByTestId("puck")).toBeNull()
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/pages/about"))).toBe(false)
  })

  it("asks to switch a rich-text site to blocks (confirmed PATCH), then opens the editor", async () => {
    vi.stubEnv("VITE_ENABLE_BLOCK_EDITOR", "true")
    renderAt(EDIT_URL)
    expect(await screen.findByText("This site uses the rich-text editor")).toBeDefined()
    expect(screen.queryByTestId("puck")).toBeNull()

    fireEvent.click(screen.getByRole("button", { name: "Switch to block editor" }))
    const dialog = await screen.findByRole("alertdialog")
    fireEvent.click(Array.from(dialog.querySelectorAll("button")).find((b) => b.textContent === "Switch to block editor")!)

    // Legacy body is shown as one raw-HTML RichText block.
    expect((await screen.findByTestId("puck")).textContent).toBe("RichText:legacy")
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH")
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ editor: "blocks" })
  })

  it("opens the editor directly for a blocks site", async () => {
    vi.stubEnv("VITE_ENABLE_BLOCK_EDITOR", "true")
    site.editor = "blocks"
    renderAt(EDIT_URL)
    expect((await screen.findByTestId("puck")).textContent).toBe("RichText:legacy")
    expect(screen.queryByText("This site uses the rich-text editor")).toBeNull()
  })
})

describe("doc <-> Puck data", () => {
  it("toDoc keeps only catalog types/props and maps 400 paths to block names", async () => {
    const { toDoc, describeDocPath } = await import("@/editor/puck-config")
    const doc = toDoc({
      root: { props: { title: "About", extra: 1 } },
      content: [
        { type: "Hero", props: { id: "h1", heading: "Hi", puckOnly: true } },
        { type: "Nope", props: { id: "x" } },
        { type: "Columns", props: { id: "c1", count: 2, col_0: [{ type: "Divider", props: { id: "d1" } }] } },
      ],
      zones: {},
    } as never)
    expect(doc).toEqual({
      schema: 1,
      root: { props: { title: "About", meta_description: "" } },
      content: [
        { type: "Hero", props: { id: "h1", heading: "Hi" } },
        {
          type: "Columns",
          props: { id: "c1", count: 2, col_0: [{ type: "Divider", props: { id: "d1" } }], col_1: [], col_2: [] },
        },
      ],
    })
    expect(describeDocPath(doc, "content[1].props.col_0[0].props.size")).toBe(
      "Block 2 (Columns) › Column 1, block 1 (Divider) › size"
    )
  })
})
