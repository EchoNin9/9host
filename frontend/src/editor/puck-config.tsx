/**
 * Puck config for the block catalog v1 (ADR-0003 §1; api/blocks/catalog.py).
 * Rendering is shared with the golden-tested React blocks (editor/blocks.tsx); fields
 * use our pickers (editor/fields.tsx) and the TipTap RichTextEditor.
 */
import type { Config, Data, Field } from "@puckeditor/core"
import type { BlockDoc, BlockItem } from "@/editor/block-env"
import { BLOCK_DEFAULTS, SLOTS } from "@/editor/blocks"
import { BlockCanvas, CtaPicker, LinkPicker, MediaListPicker, MediaPicker, RichTextField } from "@/editor/fields"

type P = Record<string, unknown>

const text = (label: string): Field => ({ type: "text", label })
const textarea = (label: string): Field => ({ type: "textarea", label })
const select = (label: string, options: [string | number, string][]): Field => ({
  type: "select",
  label,
  options: options.map(([value, l]) => ({ value, label: l })),
})
const custom = (label: string, render: (p: { value: never; onChange: (v: unknown) => void; id: string }) => React.ReactElement): Field => ({
  type: "custom",
  label,
  render: ({ value, onChange, id }) => render({ value: value as never, onChange, id }),
})

const mediaField = (label: string) => custom(label, ({ value, onChange }) => <MediaPicker value={value} onChange={onChange} />)
const ctaField = (label: string) => custom(label, ({ value, onChange }) => <CtaPicker value={value} onChange={onChange} />)
const count = (label: string): Field => ({ type: "number", label, min: 1, max: 20 })

const FIELDS: Record<string, Record<string, Field>> = {
  Hero: {
    heading: text("Heading"),
    subheading: textarea("Subheading"),
    image: mediaField("Image"),
    cta: ctaField("Button"),
    align: select("Alignment", [["center", "Centered"], ["left", "Left"]]),
  },
  RichText: {
    html: custom("Text", ({ value, onChange }) => <RichTextField value={value} onChange={onChange} />),
  },
  Image: {
    image: mediaField("Image"),
    alt: text("Alt text (describe the image)"),
    caption: text("Caption"),
    size: select("Size", [["full", "Full width"], ["medium", "Medium"], ["small", "Small"]]),
  },
  Gallery: {
    source: select("Images", [["selected", "Chosen images"], ["all", "All site media"]]),
    items: custom("Chosen images", ({ value, onChange }) => <MediaListPicker value={value} onChange={onChange} />),
    columns: select("Columns", [[2, "2"], [3, "3"], [4, "4"]]),
  },
  Columns: {
    count: select("Columns", [[2, "2 columns"], [3, "3 columns"]]),
    col_0: { type: "slot", label: "Column 1" },
    col_1: { type: "slot", label: "Column 2" },
    col_2: { type: "slot", label: "Column 3" },
  },
  CallToAction: {
    heading: text("Heading"),
    text: textarea("Text"),
    button: ctaField("Button"),
    variant: select("Style", [["primary", "Primary"], ["secondary", "Secondary"]]),
  },
  Divider: {},
  Spacer: { size: select("Size", [["sm", "Small"], ["md", "Medium"], ["lg", "Large"]]) },
  PostList: { heading: text("Heading"), count: count("Number of posts") },
  EventList: { heading: text("Heading"), count: count("Number of events") },
  LinkList: {
    heading: text("Heading"),
    items: {
      type: "array",
      label: "Links",
      max: 50,
      arrayFields: {
        label: text("Label"),
        link: custom("Link to", ({ value, onChange, id }) => <LinkPicker id={id} value={value} onChange={onChange} />),
      },
      defaultItemProps: { label: "Link", link: { kind: "home" } },
      getItemSummary: (item: { label?: string }) => item?.label || "Link",
    },
  },
  Embed: {
    provider: select("Provider", [["youtube", "YouTube"], ["vimeo", "Vimeo"], ["google_maps", "Google Maps"]]),
    embed_id: text("Video id or map search (e.g. dQw4w9WgXcQ)"),
    title: text("Title (for screen readers)"),
  },
}

const LABELS: Record<string, string> = {
  RichText: "Text",
  CallToAction: "Call to action",
  PostList: "Latest posts",
  EventList: "Upcoming events",
  LinkList: "Links",
}

export const blockLabel = (type: string) => LABELS[type] ?? type

/** "content[1].props.col_0[0].props.heading" -> "Block 2 (Columns) › Column 1, block 1 (Hero) › heading". */
export function describeDocPath(doc: BlockDoc, path: string): string {
  const parts: string[] = []
  let block: BlockItem | undefined
  for (const [, name, idx] of path.matchAll(/([A-Za-z_]\w*)(?:\[(\d+)\])?/g)) {
    if (name === "props") continue
    if (name === "root") {
      parts.push("Page settings")
    } else if (idx !== undefined && (name === "content" || /^col_\d$/.test(name))) {
      const list = (name === "content" ? doc.content : (block?.props?.[name] as BlockItem[])) ?? []
      block = list[Number(idx)]
      const where = name === "content" ? "Block" : `Column ${Number(name.slice(4)) + 1}, block`
      parts.push(`${where} ${Number(idx) + 1}${block ? ` (${blockLabel(block.type)})` : ""}`)
    } else {
      parts.push(name.replace(/_/g, " ") + (idx !== undefined ? ` ${Number(idx) + 1}` : ""))
    }
  }
  return parts.join(" › ")
}

const SAMPLE_PROPS: Record<string, P> = {
  Hero: { heading: "Welcome" },
  RichText: { html: "<p>Write something…</p>" },
  CallToAction: { heading: "Ready to talk?", button: { label: "Contact us", link: { kind: "home" } } },
  PostList: { heading: "Latest posts" },
  EventList: { heading: "Upcoming events" },
  LinkList: { heading: "Links", items: [{ label: "Home", link: { kind: "home" } }] },
}

export function makeBlockConfig(): Config {
  const components: Config["components"] = {}
  for (const type of Object.keys(BLOCK_DEFAULTS)) {
    const defaults = { ...BLOCK_DEFAULTS[type], ...SAMPLE_PROPS[type] }
    if (type === "Columns") for (const s of SLOTS) defaults[s] = []
    components[type] = {
      label: LABELS[type] ?? type,
      fields: FIELDS[type],
      defaultProps: defaults,
      render: (props: P) => <BlockCanvas type={type} props={props} />,
      ...(type === "RichText" && {
        // Editing a legacy (raw-HTML) block turns it into a normal, sanitized-on-save block.
        resolveData: (data: { props: P }, { changed, trigger }: { changed: Partial<Record<string, boolean>>; trigger: string }) =>
          data.props.legacy && changed.html && trigger !== "load"
            ? { ...data, props: { ...data.props, legacy: false } }
            : data,
      }),
    }
  }
  return {
    components,
    root: {
      fields: { title: text("Page title"), meta_description: textarea("Search description") },
      render: ({ children }: { children: React.ReactNode }) => <main className="main-content">{children}</main>,
    },
  } as Config
}

// --- doc <-> Puck data ------------------------------------------------------------------

/** Puck data -> our schema-1 doc: only known types and props (Puck UI state is dropped). */
export function toDoc(data: Data): BlockDoc {
  const clean = (items: unknown): BlockItem[] =>
    (Array.isArray(items) ? items : [])
      .filter((b) => b && typeof b.type === "string" && b.type in BLOCK_DEFAULTS)
      .map((b) => {
        const props: P = { id: b.props?.id }
        for (const k of Object.keys(BLOCK_DEFAULTS[b.type])) if (b.props?.[k] !== undefined) props[k] = b.props[k]
        if (b.type === "Columns") for (const s of SLOTS) props[s] = clean(b.props?.[s])
        return { type: b.type, props }
      })
  const root = (data.root?.props ?? {}) as P
  return {
    schema: 1,
    root: { props: { title: String(root.title ?? ""), meta_description: String(root.meta_description ?? "") } },
    content: clean(data.content),
  }
}

/** Our doc -> Puck data (Puck needs an id on every block; legacy wraps have none). */
export function toPuckData(doc: BlockDoc): Data {
  let n = 0
  const withIds = (items: unknown): BlockItem[] =>
    (Array.isArray(items) ? (items as BlockItem[]) : []).map((b) => {
      const props: P = { ...b.props, id: b.props?.id || `${b.type}-${++n}-${Date.now().toString(36)}` }
      if (b.type === "Columns") for (const s of SLOTS) props[s] = withIds(b.props?.[s])
      return { type: b.type, props }
    })
  return { root: { props: { ...(doc.root?.props ?? {}) } }, content: withIds(doc.content) as Data["content"] }
}
