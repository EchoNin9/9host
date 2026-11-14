/**
 * Full-page block editor (ADR-0003, T-31d): /:tenantSlug/sites/:siteId/pages/:pagePath/edit.
 * Lazy-loaded (Puck stays out of the entry chunk) and routed only when
 * VITE_ENABLE_BLOCK_EDITOR === "true"; usable only when site.editor === "blocks".
 * The canvas iframe loads the site template's real CSS; Save sends the block doc.
 */
import { Puck, type Data } from "@puckeditor/core"
import "@puckeditor/core/puck.css"
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft, FileQuestion, Save } from "lucide-react"
import { Button } from "@/components/ui/button"
import { EmptyState, LoadingState, Notice } from "@/components/page"
import { TenantPage, TenantPageHeader } from "@/components/tenant-page"
import { SwitchToBlocksButton } from "@/components/switch-editor-button"
import { useTenantScope } from "@/context/tenant-scope-context"
import { useSites } from "@/hooks/use-sites"
import { templateCssUrl } from "@/lib/api-client"
import {
  fetchContentEvents,
  fetchContentMedia,
  fetchContentPage,
  fetchContentPages,
  fetchContentPosts,
  fetchMediaPresignedUrl,
  getToken,
  saveContentPageDoc,
} from "@/lib/api"
import { BlockEnvContext, buildEnv, type BlockDoc, type BlockEnv } from "@/editor/block-env"
import { EditorDataContext, type EditorData } from "@/editor/editor-data"
import { describeDocPath, makeBlockConfig, toDoc, toPuckData } from "@/editor/puck-config"

interface Loaded {
  doc: BlockDoc
  isNew: boolean
  status: string
  data: EditorData
  env: BlockEnv
}

/** Adds the template stylesheet to the Puck canvas iframe. */
function CanvasCss({ doc, href, children }: { doc?: Document; href: string; children: ReactNode }) {
  useEffect(() => {
    if (!doc) return
    const link = doc.createElement("link")
    link.rel = "stylesheet"
    link.href = href
    doc.head.appendChild(link)
    return () => link.remove()
  }, [doc, href])
  return <>{children}</>
}

interface Actions {
  backTo: string
  status: string
  setStatus: (v: string) => void
  save: () => void
  saving: boolean
  label: string
}
const ActionsContext = createContext<Actions | null>(null)

/** Puck header actions: back, page status, Save. */
function HeaderActions() {
  const a = useContext(ActionsContext)
  if (!a) return null
  return (
    <>
      <Button asChild variant="ghost" size="sm">
        <Link to={a.backTo}>
          <ArrowLeft className="size-4" />
          Back
        </Link>
      </Button>
      <select
        aria-label="Page status"
        value={a.status}
        onChange={(e) => a.setStatus(e.target.value)}
        className="h-8 rounded-md border bg-card px-2 text-sm"
      >
        <option value="DRAFT">Draft</option>
        <option value="PUBLISHED">Published</option>
      </select>
      <Button size="sm" onClick={a.save} disabled={a.saving}>
        <Save className="size-4" />
        {a.label}
      </Button>
    </>
  )
}

function useEditorLoad(siteId: string, pagePath: string, enabled: boolean) {
  const { api, tenantSlug } = useTenantScope()
  const [state, setState] = useState<{ loaded?: Loaded; error?: string }>({})

  useEffect(() => {
    if (!enabled) return
    let cancelled = false
    void (async () => {
      const token = await getToken()
      const [pageRes, pages, posts, events, media] = await Promise.all([
        fetchContentPage(api, siteId, pagePath),
        fetchContentPages(api, token, siteId),
        fetchContentPosts(api, token, siteId),
        fetchContentEvents(api, token, siteId),
        fetchContentMedia(api, token, siteId),
      ])
      if (!pageRes.ok && pageRes.status !== 404) {
        if (!cancelled) setState({ error: pageRes.error })
        return
      }
      const mediaRows = await Promise.all(
        media.map(async (m) => ({ ...m, displayUrl: (await fetchMediaPresignedUrl(api, token, siteId, m.id)) ?? undefined }))
      )
      const page = pageRes.ok ? pageRes.data.page : null
      const doc: BlockDoc = page?.doc ?? {
        schema: 1,
        root: { props: { title: page?.title ?? "" } },
        // A page saved by the rich-text editor: its body as one raw-HTML text block (ADR-0003 §4).
        content: page?.body ? [{ type: "RichText", props: { html: page.body, legacy: true } }] : [],
      }
      const data: EditorData = { siteId, pages, posts, media: mediaRows }
      const env = buildEnv({ basePath: "", mediaBase: null, tenantSlug, siteId, media: mediaRows, pages, posts, events, editing: true })
      if (!cancelled)
        setState({ loaded: { doc, isNew: !page, status: page?.status?.toUpperCase() || "DRAFT", data, env } })
    })().catch(() => !cancelled && setState({ error: "Could not load the page" }))
    return () => {
      cancelled = true
    }
  }, [api, tenantSlug, siteId, pagePath, enabled])
  return state
}

function Editor({ siteId, pagePath, templateSlug, loaded, backTo }: {
  siteId: string
  pagePath: string
  templateSlug: string
  loaded: Loaded
  backTo: string
}) {
  const { api } = useTenantScope()
  const config = useMemo(() => makeBlockConfig(), [])
  const initial = useMemo(() => toPuckData(loaded.doc), [loaded.doc])
  const dataRef = useRef<Data>(initial)
  const [isNew, setIsNew] = useState(loaded.isNew)
  const [status, setStatus] = useState(loaded.status)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ tone: "success" | "danger"; title: string; where?: string } | null>(null)

  useEffect(() => {
    if (!dirty) return
    const h = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener("beforeunload", h)
    return () => window.removeEventListener("beforeunload", h)
  }, [dirty])

  const save = useCallback(async () => {
    const doc = toDoc(dataRef.current)
    setSaving(true)
    setMessage(null)
    const r = await saveContentPageDoc(api, siteId, pagePath, { status, doc }, isNew)
    setSaving(false)
    if (r.ok) {
      setIsNew(false)
      setDirty(false)
      setMessage({ tone: "success", title: "Saved. Preview the draft or publish from the content editor." })
    } else {
      setMessage({ tone: "danger", title: r.error, where: r.path ? describeDocPath(doc, r.path) : undefined })
    }
  }, [api, siteId, pagePath, status, isNew])

  const cssHref = templateCssUrl(templateSlug)
  // Stable overrides: a new iframe renderer would remount the whole canvas.
  const overrides = useMemo(
    () => ({
      iframe: ({ children, document }: { children: ReactNode; document?: Document }) => (
        <CanvasCss doc={document} href={cssHref}>
          {children}
        </CanvasCss>
      ),
      headerActions: () => <HeaderActions />,
    }),
    [cssHref]
  )
  const actions: Actions = {
    backTo,
    status,
    setStatus: (v) => {
      setStatus(v)
      setDirty(true)
    },
    save,
    saving,
    label: saving ? "Saving…" : dirty || isNew ? "Save" : "Saved",
  }

  return (
    <ActionsContext.Provider value={actions}>
      <EditorDataContext.Provider value={loaded.data}>
        <BlockEnvContext.Provider value={loaded.env}>
          <div className="flex h-svh flex-col">
            {message && (
              <Notice
                tone={message.tone}
                title={message.title}
                className="m-2"
                action={
                  <Button variant="ghost" size="sm" onClick={() => setMessage(null)}>
                    Dismiss
                  </Button>
                }
              >
                {message.where && <>Where: {message.where}</>}
              </Notice>
            )}
            <div className="min-h-0 flex-1">
              <Puck
                config={config}
                data={initial}
                onChange={(d) => {
                  dataRef.current = d
                  setDirty(true)
                }}
                overrides={overrides}
                iframe={{ enabled: true }}
                headerTitle={(loaded.doc.root?.props?.title as string) || pagePath}
                headerPath={pagePath === "_home" ? "/" : `/${pagePath}/`}
                height="100%"
              />
            </div>
          </div>
        </BlockEnvContext.Provider>
      </EditorDataContext.Provider>
    </ActionsContext.Provider>
  )
}

export default function PageEditorPage() {
  const { siteId = "", pagePath = "" } = useParams<{ siteId: string; pagePath: string }>()
  const { basePath } = useTenantScope()
  const { sites, loading, refetch } = useSites()
  const site = sites.find((s) => s.id === siteId)
  const blocks = site?.editor === "blocks"
  const { loaded, error } = useEditorLoad(siteId, pagePath, blocks)
  const backTo = `${basePath}/sites/${siteId}/edit`

  if (loading) return <TenantPage><LoadingState label="Loading site…" /></TenantPage>
  if (!site)
    return (
      <TenantPage>
        <EmptyState
          icon={FileQuestion}
          title="Site not found"
          description="It may have been deleted, or the link is out of date."
          action={<Button asChild variant="outline"><Link to={`${basePath}/sites`}>Back to sites</Link></Button>}
        />
      </TenantPage>
    )
  if (!blocks)
    return (
      <TenantPage>
        <TenantPageHeader back={{ to: backTo, label: site.name }} eyebrow="Page editor" title={`/${pagePath}/`} />
        <Notice
          tone="info"
          title="This site uses the rich-text editor"
          action={<SwitchToBlocksButton siteId={siteId} onSwitched={() => void refetch()} size="sm" />}
        >
          Switch the site to the block editor to edit this page visually.
        </Notice>
      </TenantPage>
    )
  if (error)
    return (
      <TenantPage>
        <Notice tone="danger" title="Could not open the page">{error}</Notice>
      </TenantPage>
    )
  if (!loaded) return <TenantPage><LoadingState label="Loading page…" /></TenantPage>
  return (
    <Editor
      key={`${siteId}/${pagePath}`}
      siteId={siteId}
      pagePath={pagePath}
      templateSlug={site.template_id || "business-generic"}
      loaded={loaded}
      backTo={backTo}
    />
  )
}
