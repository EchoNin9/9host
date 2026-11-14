/**
 * Block render environment + pure helpers mirroring api/blocks/core.py and
 * api/html_sanitizer.py (ADR-0003 §2-3). The Python render is the truth; these
 * keep the editor canvas close to it (parity checked by the golden-fixture Vitest).
 */
import { createContext } from "react"

export type LinkKind = "home" | "page" | "post" | "blog" | "events" | "gallery" | "external"
export interface BlockLink {
  kind: LinkKind
  path?: string
  url?: string
  new_tab?: boolean
}
export interface MediaRef {
  media_id: string
}
export interface MediaRow {
  id: string
  s3_key?: string
  caption?: string
  /** Editor only: display URL (presigned) used instead of media_base + s3_key. */
  displayUrl?: string
}
export interface PageRow {
  path: string
  title?: string
}
export interface PostRow {
  slug: string
  title?: string
  excerpt?: string
  published_at?: string | null
  created_at?: string
}
export interface EventRow {
  title?: string
  event_date?: string
  venue?: string
}

export interface BlockItem {
  type: string
  props: Record<string, unknown>
}
export interface BlockDoc {
  schema?: number
  root: { props?: { title?: string; meta_description?: string } }
  content: BlockItem[]
}

/** Python RenderContext. `mediaBase: null` (editor) keeps rich-text image URLs as stored. */
export interface BlockEnv {
  basePath: string
  mediaBase: string | null
  tenantSlug: string
  siteId: string
  media: Map<string, MediaRow>
  pages: Map<string, PageRow>
  posts: PostRow[]
  events: EventRow[]
  /** Editor canvas: show placeholders for blocks that would render nothing. */
  editing?: boolean
}

export function buildEnv(input: {
  basePath?: string
  mediaBase?: string | null
  tenantSlug?: string
  siteId?: string
  media?: MediaRow[]
  pages?: PageRow[]
  posts?: PostRow[]
  events?: EventRow[]
  editing?: boolean
}): BlockEnv {
  const pages = new Map<string, PageRow>()
  for (const p of input.pages ?? []) {
    const path = (p.path ?? "").trim().replace(/^\/+|\/+$/g, "")
    if (path) pages.set(path, p)
  }
  return {
    basePath: input.basePath ?? "",
    mediaBase: input.mediaBase === undefined ? "/media/" : input.mediaBase,
    tenantSlug: input.tenantSlug ?? "",
    siteId: input.siteId ?? "",
    media: new Map((input.media ?? []).filter((m) => m.id).map((m) => [m.id, m])),
    pages,
    posts: (input.posts ?? [])
      .filter((p) => (p.slug ?? "").trim())
      .map((p) => ({ ...p, slug: p.slug.trim() })),
    events: input.events ?? [],
    editing: input.editing,
  }
}

export const BlockEnvContext = createContext<BlockEnv>(buildEnv({}))

// --- links ------------------------------------------------------------------------------

const PATH_RE = /^[a-z0-9][a-z0-9_-]{0,99}$/
const DANGEROUS_SCHEMES = ["javascript:", "vbscript:", "data:text/html"]

function unescapeEntities(s: string): string {
  const ta = document.createElement("textarea")
  ta.innerHTML = s
  return ta.value
}

export function isDangerousUrl(url: string): boolean {
  if (!url) return false
  let cleaned = url
  for (let i = 0; i < 3; i++) {
    const next = unescapeEntities(cleaned)
    if (next === cleaned) break
    cleaned = next
  }
  // eslint-disable-next-line no-control-regex
  const normalized = cleaned.replace(/[\s\x00-\x1f\x7f-\x9f]+/g, "").toLowerCase()
  let unquoted = normalized
  try {
    unquoted = decodeURIComponent(normalized)
  } catch {
    /* keep normalized */
  }
  return DANGEROUS_SCHEMES.some((s) => normalized.startsWith(s) || unquoted.startsWith(s))
}

export function externalOk(url: string): boolean {
  return (
    /^(https?:\/\/|mailto:)/i.test(url) &&
    !isDangerousUrl(url) &&
    // eslint-disable-next-line no-control-regex
    !/[\s\x00-\x1f\x7f<>"'`\\]/.test(url) &&
    url.length <= 2048
  )
}

export function linkHref(link: BlockLink | null | undefined, basePath = ""): string {
  if (!link || typeof link !== "object") return ""
  const base = basePath.replace(/\/+$/, "")
  const path = link.path ?? ""
  if (link.kind === "home") return `${base}/`
  if (link.kind === "blog" || link.kind === "events" || link.kind === "gallery") return `${base}/${link.kind}/`
  if ((link.kind === "page" || link.kind === "post") && PATH_RE.test(path))
    return link.kind === "page" ? `${base}/${path}/` : `${base}/posts/${path}/`
  if (link.kind === "external") return externalOk(link.url ?? "") ? (link.url as string) : ""
  return ""
}

/** linkHref, but internal refs must resolve against the site's pages/posts/sections. */
export function resolveHref(link: BlockLink | null | undefined, env: BlockEnv): string {
  if (!link || typeof link !== "object") return ""
  const { kind, path } = link
  if (
    (kind === "page" && !env.pages.has(path ?? "")) ||
    (kind === "post" && !env.posts.some((p) => p.slug === path)) ||
    (kind === "blog" && env.posts.length === 0) ||
    (kind === "events" && env.events.length === 0) ||
    (kind === "gallery" && env.media.size === 0)
  )
    return ""
  return linkHref(link, env.basePath)
}

export function mediaSrc(ref: MediaRef | null | undefined, env: BlockEnv): [string, MediaRow | null] {
  const row = ref && typeof ref === "object" ? env.media.get(ref.media_id) : undefined
  if (!row) return ["", null]
  if (row.displayUrl) return [row.displayUrl, row]
  if (!row.s3_key) return ["", null]
  return [`${(env.mediaBase || "/media").replace(/\/+$/, "")}/${row.s3_key}`, row]
}

// --- rich text --------------------------------------------------------------------------

const STRIP_WITH_CONTENTS = new Set(["script", "style", "iframe", "object", "embed"])
const ALLOWED_TAGS = new Set(
  (
    "p br strong b em i u s a ul ol li h1 h2 h3 h4 h5 h6 blockquote code pre img figure figcaption hr " +
    "span div table thead tbody tr th td sup sub"
  ).split(" ")
)
const ALLOWED_ATTRS: Record<string, Set<string>> = {
  a: new Set(["href", "title", "target", "rel"]),
  img: new Set(["src", "alt", "title", "width", "height"]),
}
const SAME_CONTEXT_TARGETS = new Set(["", "_self", "_parent", "_top"])

function cleanNode(node: Node): void {
  for (const child of Array.from(node.childNodes)) {
    if (child.nodeType === Node.COMMENT_NODE) {
      child.remove()
      continue
    }
    if (child.nodeType !== Node.ELEMENT_NODE) continue
    const el = child as Element
    const tag = el.tagName.toLowerCase()
    if (STRIP_WITH_CONTENTS.has(tag)) {
      el.remove()
      continue
    }
    cleanNode(el)
    if (!ALLOWED_TAGS.has(tag)) {
      el.replaceWith(...Array.from(el.childNodes))
      continue
    }
    const allowed = ALLOWED_ATTRS[tag]
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase()
      if (
        name.startsWith("on") ||
        !allowed?.has(name) ||
        ((name === "href" || name === "src") && isDangerousUrl(attr.value))
      )
        el.removeAttribute(attr.name)
    }
    const target = el.getAttribute("target")
    if (tag === "a" && target !== null && !SAME_CONTEXT_TARGETS.has(target.trim().toLowerCase())) {
      const rel = (el.getAttribute("rel") ?? "").toLowerCase().split(/\s+/).filter(Boolean)
      for (const t of ["noopener", "noreferrer"]) if (!rel.includes(t)) rel.push(t)
      el.setAttribute("rel", Array.from(new Set(rel)).join(" "))
    }
  }
}

/** DOM port of api/html_sanitizer.sanitize_html (same allowlist; never widened). */
export function sanitizeHtml(raw: string): string {
  if (!raw || typeof raw !== "string") return ""
  const tpl = document.createElement("template")
  tpl.innerHTML = raw
  cleanNode(tpl.content)
  return tpl.innerHTML
}

/** Port of base_layout.rewrite_body_media_urls. */
export function rewriteBodyMediaUrls(body: string, tenantSlug: string, siteId: string, mediaBase: string): string {
  if (!body) return ""
  const esc = `${tenantSlug}/${siteId}/`.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  const re = new RegExp(`https?://[^\\s"'<>]*?/${esc}([^\\s"'<>?#]+)`, "gi")
  const base = (mediaBase || "/media").replace(/\/+$/, "")
  return body.replace(re, (_m, file: string) => `${base}/${tenantSlug}/${siteId}/${file}`)
}

/** Port of core.rewrite_internal_hrefs (prefix root-relative hrefs with base_path). */
export function rewriteInternalHrefs(html: string, basePath: string): string {
  const base = basePath.replace(/\/+$/, "")
  if (!base || !html) return html || ""
  return html.replace(/(\shref=")\/(?!\/)/g, `$1${base}/`)
}

/** RichText block HTML (inner content of the wrapper div). */
export function richTextHtml(html: string, legacy: boolean, env: BlockEnv): string {
  let body = html || ""
  if (env.mediaBase !== null && (!legacy || (env.tenantSlug && env.siteId)))
    body = rewriteBodyMediaUrls(body, env.tenantSlug, env.siteId, env.mediaBase)
  const clean = sanitizeHtml(body)
  return legacy ? clean : rewriteInternalHrefs(clean, env.basePath)
}

/** Python urllib.parse.quote(s, safe=""). */
export function pyQuote(s: string): string {
  return encodeURIComponent(s).replace(/[!'()*]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase())
}
