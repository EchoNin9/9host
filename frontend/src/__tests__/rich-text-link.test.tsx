/** T-31e: rich-text "Link to page" picker inserts root-relative hrefs (ADR-0003 §3). */
import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

vi.mock("@/hooks/use-tenant", () => ({ useTenant: () => ({ tenantSlug: "acme" }) }))
vi.mock("@/context/tenant-scope-context", () => ({ useTenantScope: () => ({ api: {} }) }))

import { RichTextEditor } from "@/components/ui/rich-text-editor"

// jsdom has no layout; ProseMirror's scrollIntoView calls these after a transaction (flaky in CI).
const emptyRects = () => Object.assign([], { item: () => null }) as unknown as DOMRectList
for (const proto of [Range.prototype, Element.prototype, Text.prototype] as unknown as Record<string, unknown>[]) {
  proto.getClientRects ??= emptyRects
  proto.getBoundingClientRect ??= () => new DOMRect()
}

afterEach(() => vi.unstubAllGlobals())

describe("rich-text Link to page", () => {
  it("inserts a root-relative /about/ link without target", async () => {
    const onChange = vi.fn()
    render(
      <RichTextEditor
        value="<p>Hi</p>"
        onChange={onChange}
        linkTargets={[{ label: "Home", href: "/" }, { label: "About", href: "/about/" }]}
      />
    )
    fireEvent.click(await screen.findByTitle("Link"))
    fireEvent.change(screen.getByLabelText("Link to page"), { target: { value: "/about/" } })
    await waitFor(() => expect(onChange).toHaveBeenCalled())
    const html = onChange.mock.calls.at(-1)![0] as string
    expect(html).toContain('href="/about/"')
    expect(html).not.toContain("target=")
    expect(screen.queryByLabelText("Link to page")).toBeNull()
  })

  it("without link targets keeps the plain URL prompt", async () => {
    const prompt = vi.fn(() => null)
    vi.stubGlobal("prompt", prompt)
    render(<RichTextEditor value="<p>Hi</p>" onChange={vi.fn()} />)
    fireEvent.click(await screen.findByTitle("Link"))
    expect(prompt).toHaveBeenCalledWith("URL", "https://")
    expect(screen.queryByLabelText("Link to page")).toBeNull()
  })
})
