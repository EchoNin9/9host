/**
 * Custom Puck fields for the closed prop types (ADR-0003 §1): link, media, media list,
 * call-to-action and rich text. Values are the stored shapes ({kind, path?|url?},
 * {media_id}); users only see pickers, never JSON.
 */
import { useContext, type ComponentType } from "react"
import { Check } from "lucide-react"
import { Input } from "@/components/ui/input"
import { NativeSelect } from "@/components/ui/native-select"
import { RichTextEditor } from "@/components/ui/rich-text-editor"
import { EditorDataContext } from "@/editor/editor-data"
import { BlockEnvContext, type BlockLink, type LinkKind, type MediaRef } from "@/editor/block-env"
import { renderBlock } from "@/editor/blocks"

type P = Record<string, unknown>

const KINDS: { value: LinkKind | ""; label: string }[] = [
  { value: "", label: "No link" },
  { value: "home", label: "Home page" },
  { value: "page", label: "A page" },
  { value: "post", label: "A blog post" },
  { value: "blog", label: "Blog" },
  { value: "events", label: "Events" },
  { value: "gallery", label: "Gallery" },
  { value: "external", label: "Web address" },
]

export function LinkPicker({
  value,
  onChange,
  id,
}: {
  value: BlockLink | null | undefined
  onChange: (v: BlockLink | null) => void
  id?: string
}) {
  const { pages, posts } = useContext(EditorDataContext)
  const kind = value?.kind ?? ""
  return (
    <div className="grid gap-2">
      <NativeSelect
        id={id}
        aria-label="Link to"
        value={kind}
        onChange={(e) => {
          const k = e.target.value as LinkKind | ""
          onChange(k ? { kind: k, ...(k === "external" ? { url: "https://" } : {}) } : null)
        }}
      >
        {KINDS.map((k) => (
          <option key={k.value} value={k.value}>
            {k.label}
          </option>
        ))}
      </NativeSelect>
      {(kind === "page" || kind === "post") && (
        <NativeSelect
          aria-label={kind === "page" ? "Page" : "Post"}
          value={value?.path ?? ""}
          onChange={(e) => onChange({ kind, path: e.target.value })}
        >
          <option value="">Choose…</option>
          {kind === "page"
            ? pages
                .filter((p) => p.path !== "_home")
                .map((p) => (
                  <option key={p.path} value={p.path}>
                    {p.title || p.path} (/{p.path}/)
                  </option>
                ))
            : posts.map((p) => (
                <option key={p.slug} value={p.slug}>
                  {p.title || p.slug}
                </option>
              ))}
        </NativeSelect>
      )}
      {kind === "external" && (
        <>
          <Input
            aria-label="Web address"
            value={value?.url ?? ""}
            placeholder="https://example.com or mailto:you@example.com"
            onChange={(e) => onChange({ ...value, kind: "external", url: e.target.value })}
          />
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={!!value?.new_tab}
              onChange={(e) => onChange({ ...value, kind: "external", new_tab: e.target.checked })}
            />
            Open in a new tab
          </label>
        </>
      )}
    </div>
  )
}

type Cta = { label: string; link: BlockLink | null } | null

export function CtaPicker({ value, onChange }: { value: Cta | undefined; onChange: (v: Cta) => void }) {
  return (
    <div className="grid gap-2">
      <Input
        aria-label="Button label"
        placeholder="Button label (leave empty for no button)"
        value={value?.label ?? ""}
        onChange={(e) => onChange({ label: e.target.value, link: value?.link ?? null })}
      />
      <LinkPicker value={value?.link} onChange={(link) => onChange({ label: value?.label ?? "", link })} />
    </div>
  )
}

function Thumb({ url, label, selected, onClick }: { url?: string; label: string; selected: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      title={label}
      className={`relative aspect-square overflow-hidden rounded-md border bg-muted ${
        selected ? "border-primary ring-2 ring-primary/40" : "hover:border-input"
      }`}
    >
      {url ? <img src={url} alt={label} className="size-full object-cover" /> : <span className="text-xs">{label}</span>}
      {selected && (
        <span className="absolute top-1 right-1 rounded-full bg-primary p-0.5 text-primary-foreground">
          <Check className="size-3" />
        </span>
      )}
    </button>
  )
}

function NoMedia() {
  return (
    <p className="text-xs text-muted-foreground">
      No images yet. Upload them in the site’s Media tab, then come back.
    </p>
  )
}

export function MediaPicker({
  value,
  onChange,
}: {
  value: MediaRef | null | undefined
  onChange: (v: MediaRef | null) => void
}) {
  const { media } = useContext(EditorDataContext)
  if (!media.length) return <NoMedia />
  return (
    <div className="grid grid-cols-3 gap-2">
      {media.map((m) => (
        <Thumb
          key={m.id}
          url={m.displayUrl}
          label={m.caption || m.s3_key?.split("/").pop() || m.id}
          selected={value?.media_id === m.id}
          onClick={() => onChange(value?.media_id === m.id ? null : { media_id: m.id })}
        />
      ))}
    </div>
  )
}

export function MediaListPicker({
  value,
  onChange,
}: {
  value: MediaRef[] | undefined
  onChange: (v: MediaRef[]) => void
}) {
  const { media } = useContext(EditorDataContext)
  const list = value ?? []
  if (!media.length) return <NoMedia />
  return (
    <div className="grid gap-1">
      <p className="text-xs text-muted-foreground">Click images to add or remove them (shown in click order).</p>
      <div className="grid grid-cols-3 gap-2">
        {media.map((m) => {
          const on = list.some((r) => r.media_id === m.id)
          return (
            <Thumb
              key={m.id}
              url={m.displayUrl}
              label={m.caption || m.s3_key?.split("/").pop() || m.id}
              selected={on}
              onClick={() => onChange(on ? list.filter((r) => r.media_id !== m.id) : [...list, { media_id: m.id }])}
            />
          )
        })}
      </div>
    </div>
  )
}

export function RichTextField({ value, onChange }: { value: string | undefined; onChange: (v: string) => void }) {
  const { siteId } = useContext(EditorDataContext)
  return <RichTextEditor value={value ?? ""} onChange={onChange} siteId={siteId} />
}

const HINTS: Record<string, string> = {
  Hero: "Hero — add a heading, image or button",
  Image: "Image — choose an image",
  Gallery: "Gallery — choose images (or show all site media)",
  LinkList: "Links — add links to pages or web addresses",
  Embed: "Embed — enter a valid video or map id",
}

/** Puck render for a block: the shared React block, or an editor-only placeholder when it renders nothing. */
export function BlockCanvas({ type, props }: { type: string; props: P }) {
  const env = useContext(BlockEnvContext)
  const el = renderBlock(type, props, env, (s) => {
    const Slot = props[s] as ComponentType<{ className?: string }> | undefined
    return Slot ? <Slot key={s} className="b-columns__col" /> : <div key={s} className="b-columns__col" />
  })
  if (el) return el
  return env.editing ? (
    <div
      style={{ padding: "1rem", border: "1px dashed #9ca3af", borderRadius: 6, color: "#6b7280", fontSize: 14 }}
    >
      {HINTS[type] ?? type}
    </div>
  ) : (
    <></>
  )
}
