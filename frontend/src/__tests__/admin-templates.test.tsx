/**
 * T-32b: superadmin template list + full-page editor (ADR-0003 §5). Token validation mirrors
 * api/templates/base_layout.py; the editor saves versions, publishes/upgrades behind a confirm,
 * and previews in a sandboxed (script-less) srcdoc iframe. Fetch is mocked (ApiClient transport).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"

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
  useAdminTenants: () => ({ isSuperadmin: true, loading: false, tenants: [], error: null, refetch: vi.fn() }),
}))
vi.mock("@/hooks/use-tenants", () => ({
  useTenants: () => ({ tenants: [], loading: false, refetch: vi.fn() }),
}))
// Puck is not exercised in jsdom: the stub shows the preset blocks and the offered components.
vi.mock("@puckeditor/core", () => ({
  Puck: ({ data, config }: { data: { content: { type: string }[] }; config: { categories: { allowed: { components: string[] } } } }) => (
    <div data-testid="puck">
      {data.content.map((b) => b.type).join(",")}|{config.categories.allowed.components.join(",")}
    </div>
  ),
}))

import App from "@/App"
import { presetPathError, templateTokensCss, toColorInput, tokenError, tokenErrors } from "@/lib/template-tokens"
import { describeTemplatePath, emptyDraft } from "@/editor/template-data"

const HEAD = {
  slug: "bold",
  name: "Bold",
  description: "Big type",
  tier_required: "PRO",
  base_renderer: "business-generic",
  latest_version: 2,
  published_version: 1,
  deprecated: false,
  updated_at: "2026-11-01T00:00:00Z",
  versions: [
    { version: 1, created_at: "2026-10-01T00:00:00Z", published: true },
    { version: 2, created_at: "2026-11-01T00:00:00Z", published: false },
  ],
}
const V2 = {
  version: 2,
  tokens: { primary: "#112233" },
  allowed_blocks: { Hero: true, RichText: true },
  page_presets: {
    _home: { schema: 1, root: { props: { title: "Home" } }, content: [{ type: "Hero", props: { id: "h1", heading: "Hi" } }] },
    about: { schema: 1, root: { props: { title: "About" } }, content: [] },
  },
  header: { show_logo: true, nav_style: "default" },
  footer: { text: "© Bold", links: [] },
}

const fetchMock = vi.fn()
const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }))
const sent = (method: string, path: string) =>
  fetchMock.mock.calls
    .filter(([u, init]) => (init?.method ?? "GET") === method && new URL(u).pathname === path)
    .map(([, init]) => JSON.parse(String(init.body)))

beforeEach(() => {
  fetchMock.mockReset()
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    const path = new URL(url).pathname
    const method = init?.method ?? "GET"
    if (path === "/api/admin/templates") return method === "POST" ? json(HEAD, 201) : json({ templates: [HEAD] })
    if (path === "/api/admin/templates/bold" && method === "GET") return json(HEAD)
    if (path === "/api/admin/templates/bold/versions/2") return json(V2)
    if (path === "/api/admin/templates/bold/versions/1") return json({ ...V2, version: 1, tokens: {} })
    if (path === "/api/admin/templates/bold/versions" && method === "POST")
      return json({ ...V2, ...JSON.parse(String(init!.body)), version: 3 }, 201)
    if (path === "/api/admin/templates/bold/publish")
      return json({ ...HEAD, published_version: 2, versions: HEAD.versions.map((v) => ({ ...v, published: v.version === 2 })) })
    if (path === "/api/admin/templates/bold/upgrade-sites") return json({ version: 2, updated: 3, sites: [] })
    if (path === "/api/admin/templates/bold/preview")
      return json({ html: "<html><body><h1>Sample Site</h1><script>alert(1)</script></body></html>", version: 2, preset: "_home" })
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

describe("token validation (mirrors base_layout TEMPLATE_TOKENS)", () => {
  it("accepts and rejects the same values as the backend regexes", () => {
    expect(tokenError("primary", "#2563eb")).toBeNull()
    expect(tokenError("primary", "#abc")).toBeNull()
    expect(tokenError("bg", "#11223344")).toBeNull()
    expect(tokenError("primary", "red")).toMatch(/hex/)
    expect(tokenError("primary", "#12")).toMatch(/hex/)
    expect(tokenError("text", "#123456789")).toMatch(/hex/)
    expect(tokenError("body_font", "Georgia, 'Times New Roman', serif")).toBeNull()
    expect(tokenError("body_font", 'Georgia; } body { color: red')).not.toBeNull()
    expect(tokenError("heading_font", "x".repeat(101))).not.toBeNull()
    expect(tokenError("radius", "8px")).toBeNull()
    expect(tokenError("spacing", "1.25rem")).toBeNull()
    expect(tokenError("radius", "100px")).not.toBeNull()
    expect(tokenError("spacing", "1.255rem")).not.toBeNull()
    expect(tokenError("radius", "8em")).not.toBeNull()
    expect(tokenError("radius", "")).toBeNull()
    expect(Object.keys(tokenErrors({ primary: "nope", radius: "8px" }))).toEqual(["primary"])
  })

  it("emits the same CSS as template_tokens_css and skips invalid values", () => {
    expect(templateTokensCss({})).toBe("")
    expect(templateTokensCss({ primary: "#f00", radius: "8px", body_font: "Georgia, serif", bg: "bad" })).toBe(
      "\n/* Template tokens (ADR-0003 §5) */\n:root {\n  --template-primary: #f00;\n  --template-body-font: Georgia, serif;\n" +
        "  --template-radius: 8px;\n}\nbody { font-family: var(--brand-font, var(--template-body-font)); }\n"
    )
  })

  it("normalizes colours for the native colour input and validates preset paths", () => {
    expect(toColorInput("#AbC")).toBe("#aabbcc")
    expect(toColorInput("#11223344")).toBe("#112233")
    expect(toColorInput("oops")).toBe("#000000")
    expect(presetPathError("about-us")).toBeNull()
    expect(presetPathError("About")).not.toBeNull()
    expect(presetPathError("blog")).toMatch(/reserved/)
    expect(presetPathError("admin")).toMatch(/reserved/)
    expect(presetPathError("about", ["about"])).toMatch(/exists/)
  })

  it("describes backend error paths in words", () => {
    const d = { ...emptyDraft(), page_presets: V2.page_presets }
    expect(describeTemplatePath("tokens.primary", d)).toBe("Theme › Primary")
    expect(describeTemplatePath("page_presets._home.content[0].props.heading", d)).toBe("Page “Home” › Block 1 (Hero) › heading")
    expect(describeTemplatePath("footer.links[0].link.url", d)).toBe("Footer › links 1 › link › url")
  })
})

describe("template list → full-page editor", () => {
  it("lists templates without a side sheet and opens the editor route", async () => {
    renderAt("/admin/templates")
    expect(await screen.findByText("Bold")).toBeTruthy()
    expect(screen.getByText(/Published v1/)).toBeTruthy()
    expect(document.querySelector('[data-slot="sheet-content"]')).toBeNull()
    fireEvent.click(screen.getByRole("link", { name: "Edit Bold" }))
    expect(await screen.findByRole("heading", { name: "Bold" })).toBeTruthy()
    expect(window.location.pathname).toBe("/admin/templates/bold/edit")
    expect(((await screen.findByLabelText("Primary")) as HTMLInputElement).value).toBe("#112233")
    // No raw JSON anywhere on the page.
    expect(document.body.textContent).not.toMatch(/"page_presets"|\{"/)
  })

  it("creates a template from the inline form and opens its editor", async () => {
    fetchMock.mockImplementationOnce(() => json({ templates: [] }))
    renderAt("/admin/templates")
    fireEvent.click(await screen.findByRole("button", { name: /New template/ }))
    fireEvent.change(screen.getByLabelText("Slug"), { target: { value: "Bold" } })
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Bold" } })
    fireEvent.click(screen.getByRole("button", { name: "Create and edit" }))
    await waitFor(() => expect(window.location.pathname).toBe("/admin/templates/bold/edit"))
    expect(sent("POST", "/api/admin/templates")[0]).toEqual({
      slug: "bold",
      name: "Bold",
      tier_required: "FREE",
      base_renderer: "business-generic",
    })
  })
})

describe("template editor", () => {
  it("saves a new version with every versioned field", async () => {
    renderAt("/admin/templates/bold/edit")
    const primary = await screen.findByLabelText("Primary")
    fireEvent.change(primary, { target: { value: "#ff0000" } })
    fireEvent.change(screen.getByLabelText("Corner radius"), { target: { value: "12px" } })
    fireEvent.click(screen.getByRole("button", { name: "Save as new version" }))
    await screen.findByText(/Saved as v3/)
    expect(sent("POST", "/api/admin/templates/bold/versions")).toEqual([
      {
        tokens: { primary: "#ff0000", radius: "12px" },
        allowed_blocks: V2.allowed_blocks,
        page_presets: V2.page_presets,
        header: V2.header,
        footer: V2.footer,
      },
    ])
  })

  it("blocks saving invalid tokens and shows where", async () => {
    renderAt("/admin/templates/bold/edit")
    fireEvent.change(await screen.findByLabelText("Primary"), { target: { value: "blue" } })
    expect(screen.getByText(/Use a hex colour/)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Save as new version" }))
    expect(await screen.findByText(/Where: Theme › Primary/)).toBeTruthy()
    expect(sent("POST", "/api/admin/templates/bold/versions")).toEqual([])
  })

  it("shows a backend 400 path in words", async () => {
    renderAt("/admin/templates/bold/edit")
    fireEvent.change(await screen.findByLabelText("Footer text"), { target: { value: "changed" } })
    fetchMock.mockImplementationOnce(() => json({ error: "invalid path", path: "page_presets._home.content[0].props.heading" }, 400))
    fireEvent.click(screen.getByRole("button", { name: "Save as new version" }))
    expect(await screen.findByText(/Where: Page “Home” › Block 1 \(Hero\) › heading/)).toBeTruthy()
  })

  it("publishes and upgrades only after confirming", async () => {
    renderAt("/admin/templates/bold/edit")
    fireEvent.click(await screen.findByRole("button", { name: "Publish v2" }))
    const dialog = await screen.findByRole("alertdialog")
    expect(sent("POST", "/api/admin/templates/bold/publish")).toEqual([])
    fireEvent.click(within(dialog).getByRole("button", { name: "Publish v2" }))
    await screen.findByText(/v2 is published/)
    expect(sent("POST", "/api/admin/templates/bold/publish")).toEqual([{ version: 2 }])

    fireEvent.click(screen.getByRole("button", { name: "Upgrade all sites" }))
    const upgrade = await screen.findByRole("alertdialog")
    expect(within(upgrade).getByText("Upgrade all sites to v2?")).toBeTruthy()
    fireEvent.click(within(upgrade).getByRole("button", { name: "Cancel" }))
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull())
    expect(sent("POST", "/api/admin/templates/bold/upgrade-sites")).toEqual([])
    fireEvent.click(screen.getByRole("button", { name: "Upgrade all sites" }))
    fireEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Upgrade to v2" }))
    await screen.findByText(/3 sites moved to v2/)
    expect(sent("POST", "/api/admin/templates/bold/upgrade-sites")).toEqual([{ version: 2 }])
  })

  it("previews the sample site in a script-less sandboxed iframe", async () => {
    renderAt("/admin/templates/bold/edit")
    fireEvent.click(await screen.findByRole("button", { name: "Preview with sample site" }))
    const frame = (await screen.findByTitle("Template preview")) as HTMLIFrameElement
    expect(frame.getAttribute("sandbox")).toBe("")
    expect(frame.getAttribute("sandbox")).not.toMatch(/allow-scripts/)
    expect(frame.getAttribute("srcdoc")).toContain("Sample Site")
    expect(sent("POST", "/api/admin/templates/bold/preview")).toEqual([{ version: 2, preset: "_home" }])
  })

  it("edits presets with the shared Puck config limited to allowed blocks (flag on)", async () => {
    vi.stubEnv("VITE_ENABLE_BLOCK_EDITOR", "true")
    renderAt("/admin/templates/bold/edit")
    expect((await screen.findByTestId("puck")).textContent).toBe("Hero|Hero,RichText")
    fireEvent.click(screen.getByRole("tab", { name: "About" }))
    expect((await screen.findByTestId("puck")).textContent).toBe("|Hero,RichText")
  })

  it("hides the preset editor when the block editor flag is off", async () => {
    renderAt("/admin/templates/bold/edit")
    expect(await screen.findByText(/turned off here/)).toBeTruthy()
    expect(screen.queryByTestId("puck")).toBeNull()
    expect(screen.queryByRole("button", { name: /Add page/ })).toBeNull()
  })
})
