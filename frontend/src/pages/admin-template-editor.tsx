/**
 * Full-page template editor (T-32b, ADR-0003 §5): /admin/templates/:slug/edit (superadmin shell).
 * Left: details + theme tokens (live swatch). Center: preset pages, edited with the shared Puck
 * block config (lazy, only when VITE_ENABLE_BLOCK_EDITOR === "true") or a sandboxed sample-site
 * preview. Right: allowed blocks, header/footer, versions (publish, upgrade sites, view older).
 * Versioned data is saved as a new immutable version; users never see raw JSON.
 */
import { lazy, Suspense, useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft, Eye, Pencil, Plus, Save, X } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { NativeSelect } from "@/components/ui/native-select"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { FormField, LoadingState, Notice } from "@/components/page"
import { TenantScopeContext } from "@/context/tenant-scope-context"
import { apiClient, templateCssUrl } from "@/lib/api-client"
import {
  createTemplateVersion,
  fetchAdminTemplate,
  fetchTemplateVersion,
  previewTemplate,
  publishTemplateVersion,
  updateAdminTemplate,
  upgradeTemplateSites,
  type AdminTemplate,
  type TemplateVersion,
  type TemplateVersionData,
} from "@/lib/api"
import { isBlockEditorEnabled } from "@/lib/feature-flags"
import {
  BASE_RENDERERS,
  FONT_OPTIONS,
  HOME_PRESET,
  NAV_STYLES,
  TIERS,
  TOKENS,
  presetLabel,
  presetPathError,
  templateTokensCss,
  toColorInput,
  tokenErrors,
  type TokenKey,
  type Tokens,
} from "@/lib/template-tokens"
import { BlockEnvContext, buildEnv, type BlockDoc } from "@/editor/block-env"
import { BLOCK_NAMES, TOKEN_LABELS, describeTemplatePath, emptyDraft, normJson, versionBody, versionData } from "@/editor/template-data"
import { EditorDataContext, type EditorData } from "@/editor/editor-data"
import { LinkPicker } from "@/editor/fields"
import { blockLabel } from "@/editor/puck-config"
import { siteLinkTargets } from "@/lib/link-targets"

const PresetEditor = lazy(() => import("@/editor/template-preset-editor"))

function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <Card className="gap-3 p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{title}</h2>
        {action}
      </div>
      {children}
    </Card>
  )
}

// --- left panel ----------------------------------------------------------------------------

function DetailsForm({ head, base, setBase, onSaved }: {
  head: AdminTemplate
  base: string
  setBase: (v: string) => void
  onSaved: (h: AdminTemplate) => void
}) {
  const [name, setName] = useState(head.name)
  const [description, setDescription] = useState(head.description)
  const [tier, setTier] = useState(head.tier_required)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const changed =
    name !== head.name || description !== head.description || tier !== head.tier_required || base !== (head.base_renderer ?? "")

  const save = async (body: Parameters<typeof updateAdminTemplate>[1]) => {
    setSaving(true)
    setError(null)
    const r = await updateAdminTemplate(head.slug, body)
    setSaving(false)
    if (!r.ok) return setError(r.error)
    onSaved(r.data)
    setSaved(true)
  }

  return (
    <Section title="Details">
      <FormField label="Name" htmlFor="tpl-name">
        <Input id="tpl-name" value={name} onChange={(e) => (setName(e.target.value), setSaved(false))} />
      </FormField>
      <FormField label="Description" htmlFor="tpl-desc">
        <Textarea id="tpl-desc" rows={2} value={description} onChange={(e) => (setDescription(e.target.value), setSaved(false))} />
      </FormField>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="Tier required" htmlFor="tpl-tier">
          <NativeSelect id="tpl-tier" value={tier} onChange={(e) => (setTier(e.target.value), setSaved(false))}>
            {TIERS.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </NativeSelect>
        </FormField>
        <FormField label="Base design" htmlFor="tpl-base">
          <NativeSelect id="tpl-base" value={base} onChange={(e) => (setBase(e.target.value), setSaved(false))}>
            {!base && <option value="">Choose…</option>}
            {BASE_RENDERERS.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </NativeSelect>
        </FormField>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          disabled={saving || !changed || !name.trim() || !base}
          onClick={() => void save({ name: name.trim(), description, tier_required: tier, base_renderer: base })}
        >
          {saving ? "Saving…" : "Save details"}
        </Button>
        {saved && !changed && <span className="text-xs text-muted-foreground">Saved</span>}
      </div>
      <label className="flex items-center justify-between gap-3 border-t pt-3 text-sm">
        <span>
          <span className="block font-medium">Deprecated</span>
          <span className="block text-xs text-muted-foreground">Hidden for new sites; existing sites keep it.</span>
        </span>
        <Switch
          aria-label="Deprecated"
          checked={head.deprecated}
          disabled={saving}
          onCheckedChange={(v) => void save({ deprecated: v })}
        />
      </label>
    </Section>
  )
}

function TokenInput({ k, value, error, onChange }: { k: (typeof TOKENS)[number]; value: string; error?: string; onChange: (v: string) => void }) {
  const id = `token-${k.key}`
  return (
    <FormField label={k.label} htmlFor={id} error={error}>
      {k.kind === "color" ? (
        <div className="flex gap-2">
          <input
            type="color"
            aria-label={`${k.label} colour picker`}
            value={toColorInput(value)}
            onChange={(e) => onChange(e.target.value)}
            className="h-9 w-10 shrink-0 cursor-pointer rounded-md border bg-card p-1"
          />
          <Input id={id} value={value} placeholder="Default" aria-invalid={!!error} onChange={(e) => onChange(e.target.value.trim())} />
        </div>
      ) : k.kind === "font" ? (
        <NativeSelect id={id} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">Design default</option>
          {[...(value && !FONT_OPTIONS.includes(value) ? [value] : []), ...FONT_OPTIONS].map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </NativeSelect>
      ) : (
        <Input id={id} value={value} placeholder="e.g. 8px or 1rem" aria-invalid={!!error} onChange={(e) => onChange(e.target.value.trim())} />
      )}
    </FormField>
  )
}

/** Swatch driven by the same --template-* custom properties the published CSS uses. */
function TokenSwatch({ tokens }: { tokens: Tokens }) {
  const errs = tokenErrors(tokens)
  const vars: Record<string, string> = {}
  for (const t of TOKENS) if (tokens[t.key] && !errs[t.key]) vars[t.prop] = tokens[t.key]!
  return (
    <div
      data-testid="token-swatch"
      style={{
        ...vars,
        background: "var(--template-bg, #ffffff)",
        color: "var(--template-text, #111827)",
        fontFamily: "var(--template-body-font, system-ui, sans-serif)",
        padding: "var(--template-spacing, 1rem)",
        borderRadius: "var(--template-radius, 6px)",
      }}
      className="space-y-2 border"
    >
      <p style={{ fontFamily: "var(--template-heading-font, inherit)", fontWeight: 700, fontSize: "1.1rem" }}>Heading</p>
      <p className="text-sm">Body text on the page background.</p>
      <div className="flex gap-2 text-xs">
        <span style={{ background: "var(--template-primary, #2563eb)", color: "#fff", borderRadius: "var(--template-radius, 6px)", padding: "0.35rem 0.7rem" }}>
          Primary
        </span>
        <span style={{ background: "var(--template-secondary, #64748b)", color: "#fff", borderRadius: "var(--template-radius, 6px)", padding: "0.35rem 0.7rem" }}>
          Secondary
        </span>
      </div>
    </div>
  )
}

// --- right panel ---------------------------------------------------------------------------

function AllowedBlocks({ value, onChange }: { value: TemplateVersionData["allowed_blocks"]; onChange: (v: TemplateVersionData["allowed_blocks"]) => void }) {
  return (
    <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
      {BLOCK_NAMES.map((b) => (
        <label key={b} className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={!!value[b]}
            onChange={(e) => {
              const next = { ...value }
              if (e.target.checked) next[b] = true
              else delete next[b]
              onChange(next)
            }}
          />
          {blockLabel(b)}
        </label>
      ))}
    </div>
  )
}

function HeaderFooter({ data, onChange }: { data: TemplateVersionData; onChange: (p: Partial<TemplateVersionData>) => void }) {
  const links = data.footer.links ?? []
  const setLinks = (l: typeof links) => onChange({ footer: { ...data.footer, links: l } })
  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={data.header.show_logo !== false}
          onChange={(e) => onChange({ header: { ...data.header, show_logo: e.target.checked } })}
        />
        Show logo in header
      </label>
      <FormField label="Navigation style" htmlFor="tpl-nav">
        <NativeSelect id="tpl-nav" value={data.header.nav_style || "default"} onChange={(e) => onChange({ header: { ...data.header, nav_style: e.target.value } })}>
          {NAV_STYLES.map((n) => (
            <option key={n} value={n}>{n.charAt(0).toUpperCase() + n.slice(1)}</option>
          ))}
        </NativeSelect>
      </FormField>
      <FormField label="Footer text" htmlFor="tpl-footer-text">
        <Textarea id="tpl-footer-text" rows={2} maxLength={500} value={data.footer.text ?? ""} onChange={(e) => onChange({ footer: { ...data.footer, text: e.target.value } })} />
      </FormField>
      <div className="space-y-2">
        <p className="text-sm font-medium">Footer links</p>
        {links.map((l, i) => (
          <div key={i} className="space-y-1.5 rounded-md border p-2">
            <div className="flex gap-2">
              <Input
                aria-label={`Footer link ${i + 1} label`}
                value={l.label}
                maxLength={100}
                placeholder="Label"
                onChange={(e) => setLinks(links.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))}
              />
              <Button size="icon-sm" variant="ghost" aria-label={`Remove footer link ${i + 1}`} onClick={() => setLinks(links.filter((_, j) => j !== i))}>
                <X className="size-4" />
              </Button>
            </div>
            <LinkPicker value={l.link} onChange={(link) => setLinks(links.map((x, j) => (j === i ? { ...x, link } : x)))} />
          </div>
        ))}
        {links.length < 20 && (
          <Button size="sm" variant="outline" onClick={() => setLinks([...links, { label: "", link: { kind: "home" } }])}>
            <Plus className="size-4" />
            Add link
          </Button>
        )}
      </div>
    </div>
  )
}

// --- page ----------------------------------------------------------------------------------

type Msg = { tone: "success" | "danger" | "info"; title: string; where?: string }
type Confirm = { kind: "publish" | "upgrade"; version: number }

/** Platform pages have no tenant: the rich-text field and pickers degrade (no uploads, no media). */
const PLATFORM_SCOPE = { tenantSlug: "", isSuperadminImpersonating: false, basePath: "", api: apiClient.forTenant("_platform") }

export default function AdminTemplateEditorPage() {
  const { slug = "" } = useParams<{ slug: string }>()
  const blockEditor = isBlockEditorEnabled()
  const [head, setHead] = useState<AdminTemplate | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [base, setBase] = useState("")
  const [draft, setDraft] = useState<TemplateVersionData>(emptyDraft)
  /** Last saved version's data (null: none yet); `dirty` is derived from it. */
  const [saved, setSaved] = useState<TemplateVersionData | null>(null)
  const [viewing, setViewing] = useState<TemplateVersion | null>(null)
  const [active, setActive] = useState(HOME_PRESET)
  const [mode, setMode] = useState<"edit" | "preview">(blockEditor ? "edit" : "preview")
  const [preview, setPreview] = useState<{ html: string; label: string } | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<Msg | null>(null)
  const [confirm, setConfirm] = useState<Confirm | null>(null)
  const [newPath, setNewPath] = useState<string | null>(null)
  const [editorKey, setEditorKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const r = await fetchAdminTemplate(slug)
      if (!r.ok) return !cancelled && setLoadError(r.error)
      let d: TemplateVersionData | null = null
      if (r.data.latest_version) {
        const v = await fetchTemplateVersion(slug, r.data.latest_version)
        if (!v.ok) return !cancelled && setLoadError(v.error)
        d = versionData(v.data)
      }
      if (cancelled) return
      setHead(r.data)
      setBase(r.data.base_renderer ?? "")
      setSaved(d)
      setDraft(d ?? emptyDraft())
    })()
    return () => {
      cancelled = true
    }
  }, [slug])

  const dirty = useMemo(() => normJson(draft) !== normJson(saved ?? emptyDraft()), [draft, saved])

  useEffect(() => {
    if (!dirty) return
    const h = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener("beforeunload", h)
    return () => window.removeEventListener("beforeunload", h)
  }, [dirty])

  const shown = viewing ? versionData(viewing) : draft
  const readOnly = !!viewing
  const presetPaths = useMemo(
    () => [HOME_PRESET, ...Object.keys(shown.page_presets).filter((p) => p !== HOME_PRESET).sort()],
    [shown.page_presets]
  )
  const activePath = presetPaths.includes(active) ? active : HOME_PRESET
  const tokens = shown.tokens as Tokens
  const errs = tokenErrors(tokens)
  const tokensCss = useMemo(() => templateTokensCss(tokens), [tokens])

  const pages = presetPaths
    .filter((p) => p !== HOME_PRESET)
    .map((p) => ({ path: p, title: shown.page_presets[p]?.root?.props?.title || presetLabel(p) }))
  const editorData: EditorData = {
    siteId: "",
    pages,
    posts: [],
    media: [],
    linkTargets: siteLinkTargets(pages),
    linkKinds: ["home", "page", "external"],
  }
  const pagesKey = JSON.stringify(pages)
  const env = useMemo(() => buildEnv({ basePath: "", mediaBase: null, pages: JSON.parse(pagesKey), editing: true }), [pagesKey])

  const update = useCallback((patch: Partial<TemplateVersionData>) => setDraft((d) => ({ ...d, ...patch })), [])
  const setToken = (k: TokenKey, v: string) => update({ tokens: { ...draft.tokens, [k]: v } })

  const onPresetChange = useCallback(
    (path: string, doc: BlockDoc) => setDraft((d) => ({ ...d, page_presets: { ...d.page_presets, [path]: doc } })),
    []
  )

  const refreshHead = async () => {
    const r = await fetchAdminTemplate(slug)
    if (r.ok) setHead(r.data)
  }

  const saveVersion = async () => {
    if (Object.keys(errs).length) {
      const [k, e] = Object.entries(errs)[0]
      return setMsg({ tone: "danger", title: e!, where: `Theme › ${TOKEN_LABELS[k]}` })
    }
    setSaving(true)
    setMsg(null)
    const r = await createTemplateVersion(slug, versionBody(draft))
    setSaving(false)
    if (!r.ok) {
      const key = r.path && /^page_presets\.([^.]+)/.exec(r.path)?.[1]
      if (key && draft.page_presets[key]) setActive(key)
      return setMsg({ tone: "danger", title: r.error, where: r.path ? describeTemplatePath(r.path, draft) : undefined })
    }
    setDraft(versionData(r.data))
    setSaved(versionData(r.data))
    setEditorKey((k) => k + 1)
    await refreshHead()
    setMsg({ tone: "success", title: `Saved as v${r.data.version}. Publish it to make it the version new sites get.` })
  }

  const runPreview = async () => {
    const version = viewing?.version ?? (head?.latest_version || undefined)
    setMode("preview")
    setPreviewing(true)
    const r = await previewTemplate(slug, { ...(version ? { version } : {}), preset: activePath })
    setPreviewing(false)
    if (!r.ok) {
      setPreview(null)
      return setMsg({ tone: "danger", title: r.error })
    }
    setPreview({ html: r.data.html, label: `${presetLabel(activePath)} · ${version ? `v${version}` : "no saved version"}` })
  }

  const view = async (n: number) => {
    if (n === head?.latest_version) {
      setViewing(null)
      return
    }
    const r = await fetchTemplateVersion(slug, n)
    if (!r.ok) return setMsg({ tone: "danger", title: r.error })
    setViewing(r.data)
    setMode("preview")
    setPreview(null)
  }

  const runConfirm = async () => {
    if (!confirm) return
    if (confirm.kind === "publish") {
      const r = await publishTemplateVersion(slug, confirm.version)
      if (!r.ok) return void setMsg({ tone: "danger", title: r.error })
      setHead(r.data)
      setMsg({ tone: "success", title: `v${confirm.version} is published. New sites start from it.` })
    } else {
      const r = await upgradeTemplateSites(slug, confirm.version)
      if (!r.ok) return void setMsg({ tone: "danger", title: r.error })
      setMsg({
        tone: "success",
        title: `${r.data.updated} site${r.data.updated === 1 ? "" : "s"} moved to v${r.data.version}. Each picks it up on its next publish.`,
      })
    }
  }

  if (loadError)
    return (
      <div className="p-6">
        <Notice tone="danger" title="Could not open the template">{loadError}</Notice>
      </div>
    )
  if (!head) return <div className="p-6"><LoadingState label="Loading template…" /></div>

  const versions = [...(head.versions ?? [])].sort((a, b) => b.version - a.version)
  const addPathError = newPath !== null ? presetPathError(newPath, presetPaths) : null

  return (
    <TenantScopeContext.Provider value={PLATFORM_SCOPE}>
      <EditorDataContext.Provider value={editorData}>
        <BlockEnvContext.Provider value={env}>
          <div className="flex flex-col gap-4 px-4 py-5 lg:px-6">
            <header className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <Link to="/admin/templates" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
                  <ArrowLeft className="size-3.5" aria-hidden />
                  Templates
                </Link>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-semibold tracking-tight">{head.name}</h1>
                  <span className="font-mono text-xs text-muted-foreground">{head.slug}</span>
                  {head.deprecated && <Badge tone="warning">Deprecated</Badge>}
                  {dirty && <Badge tone="info">Unsaved changes</Badge>}
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => void runPreview()} disabled={previewing}>
                  <Eye className="size-4" />
                  {previewing ? "Building…" : "Preview with sample site"}
                </Button>
                <Button onClick={() => void saveVersion()} disabled={saving || readOnly || (!dirty && head.latest_version > 0)}>
                  <Save className="size-4" />
                  {saving ? "Saving…" : "Save as new version"}
                </Button>
              </div>
            </header>

            {msg && (
              <Notice
                tone={msg.tone}
                title={msg.title}
                action={<Button variant="ghost" size="sm" onClick={() => setMsg(null)}>Dismiss</Button>}
              >
                {msg.where && <>Where: {msg.where}</>}
              </Notice>
            )}
            {viewing && (
              <Notice
                tone="info"
                title={`Viewing v${viewing.version} (read-only)`}
                action={
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setDraft(versionData(viewing))
                        setViewing(null)
                        setEditorKey((k) => k + 1)
                      }}
                    >
                      Use as starting point
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setViewing(null)}>Back to draft</Button>
                  </div>
                }
              >
                Saving always creates a new version; old versions never change.
              </Notice>
            )}

            <div className="grid gap-4 xl:grid-cols-[18rem_minmax(0,1fr)_18rem]">
              {/* Left: details + theme */}
              <div className="space-y-4">
                <DetailsForm head={head} base={base} setBase={setBase} onSaved={setHead} />
                <Section title="Theme">
                  <fieldset disabled={readOnly} className="space-y-3">
                    {TOKENS.map((t) => (
                      <TokenInput key={t.key} k={t} value={tokens[t.key] ?? ""} error={errs[t.key]} onChange={(v) => setToken(t.key, v)} />
                    ))}
                  </fieldset>
                  <TokenSwatch tokens={tokens} />
                </Section>
              </div>

              {/* Center: presets */}
              <Card className="min-w-0 gap-0 overflow-hidden py-0">
                <div className="flex flex-wrap items-center gap-1 border-b px-3 py-2" role="tablist" aria-label="Preset pages">
                  {presetPaths.map((p) => (
                    <Button
                      key={p}
                      role="tab"
                      aria-selected={p === activePath}
                      size="sm"
                      variant={p === activePath ? "secondary" : "ghost"}
                      onClick={() => setActive(p)}
                    >
                      {presetLabel(p)}
                    </Button>
                  ))}
                  {blockEditor && !readOnly && (
                    newPath === null ? (
                      <Button size="sm" variant="ghost" onClick={() => setNewPath("")}>
                        <Plus className="size-4" />
                        Add page
                      </Button>
                    ) : (
                      <form
                        className="flex items-center gap-1"
                        onSubmit={(e) => {
                          e.preventDefault()
                          if (addPathError) return
                          update({
                            page_presets: {
                              ...draft.page_presets,
                              [newPath]: { schema: 1, root: { props: { title: presetLabel(newPath) } }, content: [] },
                            },
                          })
                          setActive(newPath)
                          setNewPath(null)
                        }}
                      >
                        <Input
                          aria-label="New page path"
                          className="h-8 w-36"
                          placeholder="about"
                          autoFocus
                          value={newPath}
                          onChange={(e) => setNewPath(e.target.value.toLowerCase())}
                        />
                        <Button size="sm" type="submit" disabled={!!addPathError}>Add</Button>
                        <Button size="sm" type="button" variant="ghost" onClick={() => setNewPath(null)}>Cancel</Button>
                      </form>
                    )
                  )}
                  <div className="ml-auto flex items-center gap-1">
                    {blockEditor && !readOnly && activePath !== HOME_PRESET && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          const next = { ...draft.page_presets }
                          delete next[activePath]
                          update({ page_presets: next })
                          setActive(HOME_PRESET)
                        }}
                      >
                        <X className="size-4" />
                        Remove page
                      </Button>
                    )}
                    {blockEditor && !readOnly && (
                      <Button size="sm" variant={mode === "edit" ? "secondary" : "ghost"} onClick={() => setMode("edit")}>
                        <Pencil className="size-4" />
                        Edit
                      </Button>
                    )}
                    <Button size="sm" variant={mode === "preview" ? "secondary" : "ghost"} onClick={() => void runPreview()}>
                      <Eye className="size-4" />
                      Preview
                    </Button>
                  </div>
                </div>
                {newPath && addPathError && <p className="px-3 pt-2 text-xs text-destructive">{addPathError}</p>}
                <div className="h-[calc(100svh-12rem)] min-h-[560px]">
                  {mode === "edit" && blockEditor && !readOnly ? (
                    <Suspense fallback={<LoadingState className="p-4" label="Loading editor…" />}>
                      <PresetEditor
                        key={`${editorKey}:${activePath}:${base}`}
                        doc={draft.page_presets[activePath] ?? { schema: 1, root: { props: {} }, content: [] }}
                        onChange={(doc) => onPresetChange(activePath, doc)}
                        cssHref={templateCssUrl(base || "business-generic")}
                        tokensCss={tokensCss}
                        allowedBlocks={BLOCK_NAMES.filter((b) => draft.allowed_blocks[b])}
                        title={presetLabel(activePath)}
                        path={activePath === HOME_PRESET ? "/" : `/${activePath}/`}
                      />
                    </Suspense>
                  ) : preview ? (
                    <div className="flex h-full flex-col">
                      <p className="border-b px-3 py-1.5 text-xs text-muted-foreground">
                        Sample site · {preview.label}
                        {dirty && !viewing && " · unsaved changes are not included"}
                      </p>
                      <iframe title="Template preview" sandbox="" srcDoc={preview.html} className="min-h-0 w-full flex-1 bg-white" />
                    </div>
                  ) : (
                    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center text-sm text-muted-foreground">
                      {!blockEditor && <p>Preset pages are edited in the block editor, which is turned off here.</p>}
                      <Button variant="outline" onClick={() => void runPreview()} disabled={previewing}>
                        <Eye className="size-4" />
                        {previewing ? "Building…" : `Preview “${presetLabel(activePath)}” with sample site`}
                      </Button>
                    </div>
                  )}
                </div>
              </Card>

              {/* Right: blocks, chrome, versions */}
              <div className="space-y-4">
                <Section title="Versions">
                  {versions.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No versions yet. Save to create v1.</p>
                  ) : (
                    <ul className="divide-y text-sm">
                      {versions.map((v) => (
                        <li key={v.version} className="flex flex-wrap items-center gap-x-2 gap-y-1 py-2">
                          <span className="font-medium tabular-nums">v{v.version}</span>
                          {v.published && <Badge tone="success">Published</Badge>}
                          {v.version === head.latest_version && <Badge>Latest</Badge>}
                          {viewing?.version === v.version && <Badge tone="info">Viewing</Badge>}
                          <span className="ml-auto flex gap-1">
                            {v.version !== head.latest_version && (
                              <Button size="sm" variant="ghost" onClick={() => void view(v.version)}>View</Button>
                            )}
                            {!v.published ? (
                              <Button size="sm" variant="outline" onClick={() => setConfirm({ kind: "publish", version: v.version })}>
                                Publish v{v.version}
                              </Button>
                            ) : (
                              <Button size="sm" variant="outline" onClick={() => setConfirm({ kind: "upgrade", version: v.version })}>
                                Upgrade all sites
                              </Button>
                            )}
                          </span>
                          {v.created_at && (
                            <span className="w-full text-xs text-muted-foreground">{new Date(v.created_at).toLocaleString()}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </Section>
                <Section title="Allowed blocks">
                  <fieldset disabled={readOnly}>
                    <AllowedBlocks value={shown.allowed_blocks} onChange={(allowed_blocks) => update({ allowed_blocks })} />
                  </fieldset>
                </Section>
                <Section title="Header & footer">
                  <fieldset disabled={readOnly}>
                    <HeaderFooter data={shown} onChange={update} />
                  </fieldset>
                </Section>
              </div>
            </div>
          </div>

          <ConfirmDialog
            open={!!confirm}
            onOpenChange={(o) => !o && setConfirm(null)}
            destructive={false}
            title={confirm?.kind === "publish" ? `Publish v${confirm.version}?` : `Upgrade all sites to v${confirm?.version}?`}
            description={
              confirm?.kind === "publish"
                ? "New sites will start from this version. Sites already using the template stay on their version until upgraded."
                : "Every site on an older version of this template is moved to this version. Page content is not changed; theme and header/footer changes apply on each site's next publish."
            }
            confirmLabel={confirm?.kind === "publish" ? `Publish v${confirm.version}` : `Upgrade to v${confirm?.version}`}
            pendingLabel={confirm?.kind === "publish" ? "Publishing…" : "Upgrading…"}
            onConfirm={runConfirm}
          />
        </BlockEnvContext.Provider>
      </EditorDataContext.Provider>
    </TenantScopeContext.Provider>
  )
}
