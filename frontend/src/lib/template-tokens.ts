/**
 * Template data helpers (ADR-0003 §5, T-32b). Pure: mirrors api/templates/base_layout.py
 * (TEMPLATE_TOKENS regexes, template_tokens_css) and api/template_schema.py (preset paths)
 * so the admin editor validates and previews exactly what the backend accepts and emits.
 */

export const BASE_RENDERERS = [
  "business-generic",
  "musician-band",
  "personal-resume",
  "personal-tech",
  "professional-services",
] as const

export const TIERS = ["FREE", "PRO", "BUSINESS", "VIP"] as const
export const NAV_STYLES = ["default", "centered", "minimal"] as const

const COLOR_RE = /^#[0-9a-fA-F]{3,8}$/
const FONT_RE = /^[A-Za-z0-9 ,'-]{1,100}$/
const LENGTH_RE = /^\d{1,2}(\.\d{1,2})?(px|rem)$/

export type TokenKey = "primary" | "secondary" | "bg" | "text" | "heading_font" | "body_font" | "radius" | "spacing"
export type Tokens = Partial<Record<TokenKey, string>>

/** Order matches TEMPLATE_TOKENS (so the emitted CSS matches byte for byte). */
export const TOKENS: { key: TokenKey; label: string; kind: "color" | "font" | "length"; re: RegExp; prop: string }[] = [
  { key: "primary", label: "Primary", kind: "color", re: COLOR_RE, prop: "--template-primary" },
  { key: "secondary", label: "Secondary", kind: "color", re: COLOR_RE, prop: "--template-secondary" },
  { key: "bg", label: "Background", kind: "color", re: COLOR_RE, prop: "--template-bg" },
  { key: "text", label: "Text", kind: "color", re: COLOR_RE, prop: "--template-text" },
  { key: "heading_font", label: "Heading font", kind: "font", re: FONT_RE, prop: "--template-heading-font" },
  { key: "body_font", label: "Body font", kind: "font", re: FONT_RE, prop: "--template-body-font" },
  { key: "radius", label: "Corner radius", kind: "length", re: LENGTH_RE, prop: "--template-radius" },
  { key: "spacing", label: "Spacing", kind: "length", re: LENGTH_RE, prop: "--template-spacing" },
]

export const FONT_OPTIONS = [
  "system-ui, sans-serif",
  "Helvetica Neue, Arial, sans-serif",
  "Inter, sans-serif",
  "Georgia, serif",
  "Merriweather, serif",
  "Playfair Display, serif",
  "Courier New, monospace",
]

/** Error message for one token value, or null (empty = template default). */
export function tokenError(key: TokenKey, value: string | undefined): string | null {
  if (!value) return null
  const t = TOKENS.find((x) => x.key === key)
  if (!t) return "Unknown token"
  if (t.re.test(value)) return null
  if (t.kind === "color") return "Use a hex colour like #2563eb"
  if (t.kind === "font") return "Letters, numbers, spaces, commas, hyphens and ' only"
  return "Use a size like 8px or 1.5rem"
}

export function tokenErrors(tokens: Tokens): Partial<Record<TokenKey, string>> {
  const out: Partial<Record<TokenKey, string>> = {}
  for (const { key } of TOKENS) {
    const e = tokenError(key, tokens[key])
    if (e) out[key] = e
  }
  return out
}

/** Tokens without empty values (the backend drops them too). */
export function cleanTokens(tokens: Tokens): Tokens {
  const out: Tokens = {}
  for (const { key } of TOKENS) if (tokens[key]) out[key] = tokens[key]
  return out
}

/** Same output as base_layout.template_tokens_css (invalid values are skipped, never emitted). */
export function templateTokensCss(tokens: Tokens | null | undefined): string {
  if (!tokens || typeof tokens !== "object") return ""
  const props = TOKENS.filter(({ key, re }) => typeof tokens[key] === "string" && re.test(tokens[key]!)).map(
    ({ key, prop }) => `  ${prop}: ${tokens[key]};`
  )
  if (!props.length) return ""
  let css = "\n/* Template tokens (ADR-0003 §5) */\n:root {\n" + props.join("\n") + "\n}\n"
  if (props.some((p) => p.startsWith("  --template-body-font")))
    css += "body { font-family: var(--brand-font, var(--template-body-font)); }\n"
  if (props.some((p) => p.startsWith("  --template-heading-font")))
    css += "h1, h2, h3, h4 { font-family: var(--brand-font, var(--template-heading-font)); }\n"
  return css
}

/** `<input type="color">` only takes #rrggbb. */
export function toColorInput(value: string | undefined, fallback = "#000000"): string {
  if (!value || !COLOR_RE.test(value)) return fallback
  const v = value.slice(1)
  if (v.length === 3 || v.length === 4) return "#" + [...v.slice(0, 3)].map((c) => c + c).join("").toLowerCase()
  if (v.length >= 6) return "#" + v.slice(0, 6).toLowerCase()
  return fallback
}

// --- preset paths (template_schema.validate_page_presets) -------------------------------

export const HOME_PRESET = "_home"
const RESERVED_PAGE_PATHS = new Set([
  "admin", "api", "login", "signup", "auth", "signin", "signout", "logout", "register",
  "settings", "billing", "dashboard", "users", "sites", "domains", "modules", "analytics",
  "_next", "static", "assets",
])
const GENERATED_PATHS = new Set(["blog", "posts", "events", "gallery"])
/** Template slugs and page paths: lowercase alnum + hyphen. */
export const SLUG_RE = /^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/

export function presetPathError(path: string, existing: string[] = []): string | null {
  if (!path) return "Enter a page path"
  if (!SLUG_RE.test(path) || path.length > 64) return "Lowercase letters, numbers and hyphens (e.g. about-us)"
  if (RESERVED_PAGE_PATHS.has(path) || GENERATED_PATHS.has(path)) return `“${path}” is reserved`
  if (existing.includes(path)) return "That page already exists"
  return null
}

export const presetLabel = (path: string) =>
  path === HOME_PRESET ? "Home" : path.replace(/-/g, " ").replace(/^./, (c) => c.toUpperCase())
