/** Template version data helpers for the admin editor (T-32b, ADR-0003 §5). */
import type { TemplateVersion, TemplateVersionData } from "@/lib/api"
import { BLOCK_DEFAULTS } from "@/editor/blocks"
import { blockLabel, describeDocPath } from "@/editor/puck-config"
import { HOME_PRESET, TOKENS, cleanTokens, presetLabel, type Tokens } from "@/lib/template-tokens"

export const BLOCK_NAMES = Object.keys(BLOCK_DEFAULTS)

export function emptyDraft(): TemplateVersionData {
  return {
    tokens: {},
    allowed_blocks: Object.fromEntries(BLOCK_NAMES.map((b) => [b, true as const])),
    page_presets: {
      [HOME_PRESET]: { schema: 1, root: { props: { title: "Home" } }, content: [{ type: "Hero", props: { heading: "Welcome" } }] },
    },
    header: { show_logo: true, nav_style: "default" },
    footer: { text: "", links: [] },
  }
}

export const versionData = (v: TemplateVersion): TemplateVersionData => ({
  tokens: v.tokens ?? {},
  allowed_blocks: v.allowed_blocks ?? {},
  page_presets: v.page_presets ?? {},
  header: v.header ?? {},
  footer: v.footer ?? {},
})

/** The body for POST …/versions: every versioned field, tokens without empty values. */
export function versionBody(d: TemplateVersionData): TemplateVersionData {
  return {
    tokens: cleanTokens(d.tokens as Tokens) as Record<string, string>,
    allowed_blocks: d.allowed_blocks,
    page_presets: d.page_presets,
    header: d.header,
    footer: d.footer,
  }
}

/** Comparable form for dirty checks: ignores block ids and empty strings (Puck adds both). */
export const normJson = (d: TemplateVersionData) =>
  JSON.stringify(versionBody(d), (k, v) => (k === "id" || v === "" ? undefined : v))

export const TOKEN_LABELS = Object.fromEntries(TOKENS.map((t) => [t.key, t.label]))

/** Readable location for a backend 400 `path` (e.g. "page_presets.about.content[0].props.heading"). */
export function describeTemplatePath(path: string, data: TemplateVersionData): string {
  const preset = /^page_presets\.([^.]+)(?:\.(.*))?$/.exec(path)
  if (preset) {
    const [, key, rest] = preset
    const doc = data.page_presets[key]
    return [`Page “${presetLabel(key)}”`, rest && doc ? describeDocPath(doc, rest) : rest].filter(Boolean).join(" › ")
  }
  const token = /^tokens\.(\w+)$/.exec(path)
  if (token) return `Theme › ${TOKEN_LABELS[token[1]] ?? token[1]}`
  const block = /^allowed_blocks\.(\w+)$/.exec(path)
  if (block) return `Allowed blocks › ${blockLabel(block[1])}`
  return path
    .replace(/\[(\d+)\]/g, (_, n) => ` ${Number(n) + 1}`)
    .split(".")
    .map((s) => s.replace(/_/g, " "))
    .map((s, i) => (i === 0 ? s.charAt(0).toUpperCase() + s.slice(1) : s))
    .join(" › ")
}

