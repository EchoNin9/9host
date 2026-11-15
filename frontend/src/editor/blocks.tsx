/**
 * React mirrors of the 12 Python blocks (api/blocks/catalog.py). Same markup and BEM
 * classes, so the template CSS served by GET /api/templates/{slug}/css styles the
 * editor canvas the way it styles the published page. A block that Python would
 * render as "" returns null here.
 */
// Pure render helpers called as functions (no components here), so Fast Refresh boundaries do not apply.
/* eslint-disable react-refresh/only-export-components */
import { Fragment, type ReactElement, type ReactNode } from "react"
import {
  mediaSrc,
  pyQuote,
  resolveHref,
  richTextHtml,
  type BlockEnv,
  type BlockItem,
  type BlockLink,
  type MediaRef,
} from "@/editor/block-env"

type P = Record<string, unknown>
type Cta = { label?: string; link?: BlockLink | null } | null | undefined

export const BLOCK_DEFAULTS: Record<string, P> = {
  Hero: { heading: "", subheading: "", image: null, cta: null, align: "center" },
  RichText: { html: "", legacy: false },
  Image: { image: null, alt: "", caption: "", size: "full" },
  Gallery: { source: "selected", items: [], columns: 3 },
  Columns: { count: 2 },
  CallToAction: { heading: "", text: "", button: null, variant: "primary" },
  Divider: {},
  Spacer: { size: "md" },
  PostList: { heading: "", count: 5 },
  EventList: { heading: "", count: 5 },
  LinkList: { heading: "", items: [] },
  Embed: { provider: "youtube", embed_id: "", title: "" },
}

export const SLOTS = ["col_0", "col_1", "col_2"] as const

const EMBED_PATTERNS: Record<string, RegExp> = {
  youtube: /^[A-Za-z0-9_-]{11}$/,
  vimeo: /^[0-9]{1,12}$/,
  // eslint-disable-next-line no-control-regex
  google_maps: /^[^\x00-\x1f\x7f<>"`\\]{1,200}$/,
}
const EMBED_URLS: Record<string, string> = {
  youtube: "https://www.youtube-nocookie.com/embed/",
  vimeo: "https://player.vimeo.com/video/",
  google_maps: "https://www.google.com/maps?q=",
}

function withDefaults(type: string, props: P): P {
  const out: P = { ...BLOCK_DEFAULTS[type] }
  for (const [k, v] of Object.entries(props ?? {})) if (v !== undefined && v !== null) out[k] = v
  return out
}

const str = (v: unknown) => (typeof v === "string" ? v : "")

function heading(cls: string, value: unknown) {
  return str(value) ? <h2 className={cls}>{str(value)}</h2> : null
}

function img(ref: unknown, env: BlockEnv, cls: string, alt?: string) {
  const [src, row] = mediaSrc(ref as MediaRef, env)
  if (!src || !row) return null
  return <img className={cls} src={src} alt={alt ? alt : (row.caption ?? "")} />
}

function anchor(link: BlockLink | null | undefined, label: unknown, env: BlockEnv, cls: string) {
  const href = resolveHref(link, env)
  if (!href || !str(label)) return null
  const extra = link?.new_tab ? { target: "_blank", rel: "noopener noreferrer" } : {}
  return (
    <a className={cls} href={href} {...extra}>
      {str(label)}
    </a>
  )
}

function titleCase(s: string) {
  return s.replace(/\w+/g, (w) => w[0].toUpperCase() + w.slice(1).toLowerCase())
}

/**
 * Render one block. `slot(name)` renders a Columns child list (Puck passes its slot
 * components; renderDoc passes a recursive renderer).
 */
export function renderBlock(
  type: string,
  raw: P,
  env: BlockEnv,
  slot: (name: (typeof SLOTS)[number]) => ReactNode
): ReactElement | null {
  if (!(type in BLOCK_DEFAULTS)) return null
  const p = withDefaults(type, raw)
  switch (type) {
    case "Hero": {
      const cta = p.cta as Cta
      return (
        <section className={`b-hero b-hero--${str(p.align)}`}>
          {img(p.image, env, "b-hero__image")}
          {heading("b-hero__heading", p.heading)}
          {str(p.subheading) && <p className="b-hero__subheading">{str(p.subheading)}</p>}
          {anchor(cta?.link, cta?.label, env, "b-button b-hero__cta")}
        </section>
      )
    }
    case "RichText": {
      const legacy = p.legacy === true
      const __html = richTextHtml(str(p.html), legacy, env)
      return <div className={legacy ? "content" : "b-richtext content"} dangerouslySetInnerHTML={{ __html }} />
    }
    case "Image": {
      const image = img(p.image, env, "b-image__img", str(p.alt))
      if (!image) return null
      return (
        <figure className={`b-image b-image--${str(p.size)}`}>
          {image}
          {str(p.caption) && <figcaption>{str(p.caption)}</figcaption>}
        </figure>
      )
    }
    case "Gallery": {
      const refs: MediaRef[] =
        p.source === "all"
          ? Array.from(env.media.keys(), (media_id) => ({ media_id }))
          : ((p.items as MediaRef[]) ?? [])
      const figs = refs
        .map((r, i) => {
          const image = img(r, env, "b-gallery__img")
          return image && <figure key={`${r?.media_id}-${i}`}>{image}</figure>
        })
        .filter(Boolean)
      return figs.length ? <div className={`b-gallery b-gallery--${p.columns}`}>{figs}</div> : null
    }
    case "Columns": {
      const count = p.count === 3 ? 3 : 2
      return <div className={`b-columns b-columns--${count}`}>{SLOTS.slice(0, count).map((s) => slot(s))}</div>
    }
    case "CallToAction": {
      const btn = p.button as Cta
      return (
        <section className={`b-cta b-cta--${str(p.variant)}`}>
          {heading("b-cta__heading", p.heading)}
          {str(p.text) && <p className="b-cta__text">{str(p.text)}</p>}
          {anchor(btn?.link, btn?.label, env, "b-button")}
        </section>
      )
    }
    case "Divider":
      return <hr className="b-divider" />
    case "Spacer":
      return <div className={`b-spacer b-spacer--${str(p.size)}`} aria-hidden="true" />
    case "PostList": {
      const date = (x: (typeof env.posts)[number]) => String(x.published_at || x.created_at || "")
      const posts = [...env.posts]
        .sort((a, b) => (date(a) < date(b) ? 1 : date(a) > date(b) ? -1 : 0))
        .slice(0, Number(p.count))
      const base = env.basePath.replace(/\/+$/, "")
      return (
        <section className="b-postlist">
          {heading("b-postlist__heading", p.heading)}
          {posts.length ? (
            <ul className="b-postlist__list">
              {posts.map((x) => (
                <li key={x.slug}>
                  <a href={`${base}/posts/${x.slug}/`}>{x.title || x.slug}</a>
                  {x.excerpt && <p className="b-postlist__excerpt">{x.excerpt}</p>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="b-postlist__empty">No posts yet.</p>
          )}
        </section>
      )
    }
    case "EventList": {
      const events = [...env.events]
        .sort((a, b) => (String(a.event_date ?? "") < String(b.event_date ?? "") ? -1 : String(a.event_date ?? "") > String(b.event_date ?? "") ? 1 : 0))
        .slice(0, Number(p.count))
      return (
        <section className="b-eventlist">
          {heading("b-eventlist__heading", p.heading)}
          {events.length ? (
            <ul className="b-eventlist__list">
              {events.map((e, i) => (
                <li key={i}>
                  <strong>{e.title ?? ""}</strong> <span className="b-eventlist__date">{e.event_date ?? ""}</span>
                  {e.venue && (
                    <>
                      {" "}
                      <span className="b-eventlist__venue">{e.venue}</span>
                    </>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="b-eventlist__empty">No events yet.</p>
          )}
        </section>
      )
    }
    case "LinkList": {
      const items = ((p.items as { label?: string; link?: BlockLink }[]) ?? [])
        .map((it, i) => {
          const a = anchor(it?.link, it?.label, env, "b-linklist__link")
          return a && <li key={i}>{a}</li>
        })
        .filter(Boolean)
      if (!items.length) return null
      return (
        <nav className="b-linklist">
          {heading("b-linklist__heading", p.heading)}
          <ul>{items}</ul>
        </nav>
      )
    }
    case "Embed": {
      const provider = str(p.provider)
      const id = str(p.embed_id)
      if (!EMBED_PATTERNS[provider]?.test(id)) return null
      const src = EMBED_URLS[provider] + pyQuote(id) + (provider === "google_maps" ? "&output=embed" : "")
      return (
        <div className={`b-embed b-embed--${provider}`}>
          <iframe
            className="b-embed__frame"
            src={src}
            title={str(p.title) || titleCase(provider.replace(/_/g, " "))}
            loading="lazy"
            referrerPolicy="strict-origin-when-cross-origin"
            sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"
            allowFullScreen
          />
        </div>
      )
    }
  }
  return null
}

/** Render a block list (renderDoc / Columns slots) the way Python's _render_list does. */
export function renderItems(items: unknown, env: BlockEnv, depth = 1): ReactNode[] {
  if (!Array.isArray(items) || depth > 3) return []
  return (items as BlockItem[]).map((b, i) => {
    const props = (b?.props ?? {}) as P
    const el = renderBlock(b?.type, props, env, (s) => (
      <div className="b-columns__col" key={s}>
        {renderItems(props[s], env, depth + 1)}
      </div>
    ))
    return el && <Fragment key={String(props.id ?? i)}>{el}</Fragment>
  })
}
