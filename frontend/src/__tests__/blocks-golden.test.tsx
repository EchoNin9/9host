/**
 * Block parity (ADR-0003 §2): every golden fixture shared with pytest
 * (api/tests/fixtures/blocks/{name}.{mode}.json -> .html) rendered by the React blocks
 * must match the Python render after DOM normalization (attribute order, whitespace
 * between elements, void-tag syntax). The editor-only differences — Puck's slot/drag
 * wrappers and the empty-block placeholders — are not part of renderItems and are not
 * exercised here.
 */
import { describe, expect, it } from "vitest"
import { render } from "@testing-library/react"
import { buildEnv, type BlockDoc } from "@/editor/block-env"
import { renderItems } from "@/editor/blocks"

const jsonFiles = import.meta.glob("../../../api/tests/fixtures/blocks/*.json", { eager: true, import: "default" })
const htmlFiles = import.meta.glob("../../../api/tests/fixtures/blocks/*.html", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>

interface Fixture {
  mode: "live" | "draft"
  context: Parameters<typeof buildEnv>[0] & { tenant_slug: string; site_id: string; media_base: string }
  doc: BlockDoc
}

function canon(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) {
    const t = (node.textContent ?? "").replace(/\s+/g, " ")
    return t.trim() ? t : ""
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return ""
  const el = node as Element
  const attrs = Array.from(el.attributes)
    .map((a) => `${a.name}=${JSON.stringify(a.value)}`)
    .sort()
    .join(" ")
  return `<${el.tagName.toLowerCase()}${attrs ? " " + attrs : ""}>${Array.from(el.childNodes).map(canon).join("")}</>`
}

function normalize(html: string): string {
  const div = document.createElement("div")
  div.innerHTML = html
  return Array.from(div.childNodes).map(canon).join("")
}

const cases = Object.keys(jsonFiles)
  .sort()
  .map((path) => [path.split("/").pop()!.replace(/\.json$/, ""), path] as const)

describe("block goldens: React render matches Python render_doc", () => {
  it("finds every fixture pair (12 blocks x live/draft + legacy + unknown)", () => {
    expect(cases.length).toBeGreaterThanOrEqual(30)
    for (const [, path] of cases) expect(htmlFiles[path.replace(/\.json$/, ".html")]).toBeTypeOf("string")
  })

  it.each(cases)("%s", (_name, path) => {
    const fx = jsonFiles[path] as Fixture
    const env = buildEnv({
      ...fx.context,
      basePath: fx.mode === "draft" ? "/preview" : "",
      mediaBase: fx.context.media_base,
      tenantSlug: fx.context.tenant_slug,
      siteId: fx.context.site_id,
    })
    const { container } = render(<>{renderItems(fx.doc.content, env)}</>)
    const expected = htmlFiles[path.replace(/\.json$/, ".html")]
    expect(normalize(expected)).not.toBe("")
    expect(normalize(container.innerHTML)).toBe(normalize(expected))
  })
})
