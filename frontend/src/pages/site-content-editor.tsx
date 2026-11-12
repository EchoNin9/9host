import { Link, useParams, Navigate } from "react-router-dom"
import { useState } from "react"
import {
  ArrowUpRight,
  Calendar,
  Eye,
  FileQuestion,
  FileText,
  Globe,
  History,
  Image,
  LayoutTemplate,
  MoreHorizontal,
  Newspaper,
  Palette,
  Upload,
} from "lucide-react"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantScope } from "@/context/tenant-scope-context"
import { useTenantRole } from "@/hooks/use-tenant-role"
import { useSites } from "@/hooks/use-sites"
import { useIsMobile } from "@/hooks/use-mobile"
import { getToken, fetchDraftPublish, fetchDraftToken, publishSite, rollbackSite } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { ModuleLocked } from "@/components/module-locked"
import { EmptyState, FormField, LoadingState, Notice } from "@/components/page"
import { SiteStatusBadge } from "@/components/status-badges"
import { siteLiveUrl } from "@/lib/site-format"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FeatureGate } from "@/components/feature-gate"
import { PagesEditor } from "@/components/content-editors/pages-editor"
import { PostsEditor } from "@/components/content-editors/posts-editor"
import { EventsEditor } from "@/components/content-editors/events-editor"
import { MediaEditor } from "@/components/content-editors/media-editor"
import { BrandingEditor } from "@/components/content-editors/branding-editor"
import { TemplateSelector } from "@/components/content-editors/template-selector"
import { TenantPage, TenantPageHeader } from "@/components/tenant-page"

/**
 * Content editor shell (Task 2.90).
 * Layout with sidebar, page/post/event/media/branding tabs.
 * Per-module editors (2.91–2.94). Publish, draft preview and rollback (T-30) live in the header.
 */
function SiteContentEditor() {
  const { tenantSlug, tenantBasePath } = useTenant()
  const { api } = useTenantScope()
  const { siteId } = useParams<{ siteId: string }>()
  const { sites, loading, refetch } = useSites()
  const base = tenantBasePath || `/${tenantSlug}`
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [publishLoading, setPublishLoading] = useState(false)
  const [publishMessage, setPublishMessage] = useState<string | null>(null)
  const [publishError, setPublishError] = useState<string | null>(null)
  const [publishLiveUrl, setPublishLiveUrl] = useState<string | null>(null)
  const [rollbackOpen, setRollbackOpen] = useState(false)
  const [rollbackVersion, setRollbackVersion] = useState("")
  const [tab, setTab] = useState("pages")
  const { canEdit } = useTenantRole()
  const isMobile = useIsMobile()

  const site = siteId ? sites.find((s) => s.id === siteId) : null

  const handlePreviewDraft = async () => {
    if (!tenantSlug || !siteId || !site?.slug) return
    setPreviewError(null)
    setPreviewLoading(true)
    try {
      const token = await getToken()
      if (!token) {
        setPreviewError("Not authenticated")
        return
      }
      await fetchDraftPublish(api, token, siteId)
      const data = await fetchDraftToken(api, token, siteId)
      if (data?.preview_url) {
        window.open(data.preview_url, "_blank", "noopener,noreferrer")
      } else {
        setPreviewError("Could not get preview URL")
      }
    } catch {
      setPreviewError("Preview failed")
    } finally {
      setPreviewLoading(false)
    }
  }

  const handlePublish = async () => {
    if (!tenantSlug || !siteId) return
    setPublishError(null)
    setPublishMessage(null)
    setPublishLiveUrl(null)
    setPublishLoading(true)
    try {
      const token = await getToken()
      if (!token) {
        setPublishError("Not authenticated")
        return
      }
      const result = await publishSite(api, token, siteId)
      if (result) {
        const liveUrl = site ? siteLiveUrl(site) : null
        setPublishMessage(
          liveUrl
            ? `Published v${result.version} (${result.files_count} files).`
            : `Published v${result.version} (${result.files_count} files). Changes may take a few minutes to appear globally.`
        )
        if (liveUrl) setPublishLiveUrl(liveUrl)
        void refetch()
      } else {
        setPublishError("Publish returned no result")
      }
    } catch (e) {
      setPublishError(e instanceof Error ? e.message : "Publish failed")
    } finally {
      setPublishLoading(false)
    }
  }

  const openRollback = () => {
    const current = site?.published_version ?? 0
    setRollbackVersion(current > 1 ? String(current - 1) : "1")
    setRollbackOpen(true)
  }

  const handleRollback = async (): Promise<boolean> => {
    const version = Number(rollbackVersion)
    if (!siteId || !Number.isInteger(version) || version < 1) return false
    setPublishError(null)
    setPublishMessage(null)
    setPublishLiveUrl(null)
    try {
      const token = await getToken()
      const result = await rollbackSite(api, token, siteId, version)
      setPublishMessage(`Rolled back: the live site now serves v${result.version}.`)
      if (site) setPublishLiveUrl(siteLiveUrl(site))
      void refetch()
    } catch (e) {
      setPublishError(e instanceof Error ? e.message : "Rollback failed")
    }
    return true
  }

  if (!tenantSlug || !siteId) {
    return <Navigate to={base ? `${base}/sites` : "/"} replace />
  }

  if (loading) {
    return (
      <TenantPage>
        <LoadingState label="Loading site…" />
      </TenantPage>
    )
  }

  if (!site) {
    return (
      <TenantPage>
        <EmptyState
          icon={FileQuestion}
          title="Site not found"
          description="It may have been deleted, or the link is out of date."
          action={
            <Button asChild variant="outline">
              <Link to={`${base}/sites`}>Back to sites</Link>
            </Button>
          }
        />
      </TenantPage>
    )
  }

  const liveUrl = siteLiveUrl(site)
  const hasTemplate = !!site.template_id
  const canRollback = canEdit && site.published_version != null

  const tabs = [
    { value: "pages", label: "Pages", icon: FileText },
    { value: "posts", label: "Posts", icon: Newspaper },
    { value: "events", label: "Events", icon: Calendar },
    { value: "media", label: "Media", icon: Image },
    { value: "branding", label: "Branding", icon: Palette },
    { value: "templates", label: "Template", icon: LayoutTemplate },
  ] as const

  return (
    <TenantPage>
      <TenantPageHeader
        back={{ to: `${base}/sites`, label: "Sites" }}
        eyebrow="Content editor"
        title={site.name}
        meta={<SiteStatusBadge site={site} />}
        description={
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {liveUrl && site.status === "published" ? (
              <a
                href={liveUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 font-mono text-foreground underline-offset-4 hover:underline"
              >
                {liveUrl.replace("https://", "")}
                <ArrowUpRight className="size-3.5" aria-hidden />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            ) : (
              <span className="font-mono">{site.slug ? `${site.slug}.echo9.net` : site.id}</span>
            )}
            {site.published_at && (
              <span>
                · Last published {new Date(site.published_at).toLocaleString()}
              </span>
            )}
          </span>
        }
        actions={
          <>
            <Button
              variant="outline"
              onClick={handlePreviewDraft}
              disabled={previewLoading || !site.slug}
              title={!site.slug ? "Give the site a slug to preview drafts" : undefined}
            >
              <Eye className="size-4" />
              {previewLoading ? "Preparing…" : "Preview draft"}
            </Button>
            {canEdit && (
              <Button onClick={handlePublish} disabled={publishLoading || !hasTemplate}>
                <Upload className="size-4" />
                {publishLoading ? "Publishing…" : "Publish"}
              </Button>
            )}
            {canRollback && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="icon">
                    <MoreHorizontal className="size-4" />
                    <span className="sr-only">More publishing actions</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onSelect={openRollback}>
                    <History className="size-4" />
                    Roll back to an earlier version…
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </>
        }
      />

      {previewError && <Notice tone="danger">{previewError}</Notice>}
      {publishError && <Notice tone="danger" title="Publishing failed">{publishError}</Notice>}
      {publishMessage && (
        <Notice
          tone="success"
          title={publishMessage}
          action={
            publishLiveUrl && (
              <Button asChild variant="outline" size="sm">
                <a href={publishLiveUrl} target="_blank" rel="noopener noreferrer">
                  <Globe className="size-4" />
                  View live site
                </a>
              </Button>
            )
          }
        />
      )}
      {!hasTemplate && (
        <Notice
          tone="warning"
          title="Choose a template before publishing"
          action={
            <Button variant="outline" size="sm" onClick={() => setTab("templates")}>
              Choose template
            </Button>
          }
        >
          The template decides your site’s layout. Pick one in the Template tab.
        </Notice>
      )}

      <Tabs
        value={tab}
        onValueChange={setTab}
        orientation={isMobile ? "horizontal" : "vertical"}
        className="flex flex-1 flex-col gap-6 md:flex-row"
      >
        <TabsList
          variant="line"
          aria-label="Content sections"
          className="h-auto w-full shrink-0 justify-start overflow-x-auto border-b bg-transparent p-0 md:w-44 md:flex-col md:items-stretch md:overflow-visible md:border-r md:border-b-0 md:pr-3"
        >
          {tabs.map((t) => (
            <TabsTrigger key={t.value} value={t.value} className="flex-none justify-start px-3 py-2 md:w-full">
              <t.icon className="size-4" />
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="pages" className="mt-0 min-w-0 flex-1">
          <PagesEditor siteId={siteId!} />
        </TabsContent>
        <TabsContent value="posts" className="mt-0 min-w-0 flex-1">
          <FeatureGate feature="updates_blog" fallback={<ModuleLocked feature="updates_blog" />}>
            <PostsEditor siteId={siteId!} />
          </FeatureGate>
        </TabsContent>
        <TabsContent value="events" className="mt-0 min-w-0 flex-1">
          <FeatureGate feature="events_shows" fallback={<ModuleLocked feature="events_shows" />}>
            <EventsEditor siteId={siteId!} />
          </FeatureGate>
        </TabsContent>
        <TabsContent value="media" className="mt-0 min-w-0 flex-1">
          <FeatureGate feature="media_gallery" fallback={<ModuleLocked feature="media_gallery" />}>
            <MediaEditor siteId={siteId!} />
          </FeatureGate>
        </TabsContent>
        <TabsContent value="branding" className="mt-0 min-w-0 flex-1">
          <FeatureGate feature="branding" fallback={<ModuleLocked feature="branding" />}>
            <BrandingEditor site={site!} onSaved={refetch} />
          </FeatureGate>
        </TabsContent>
        <TabsContent value="templates" className="mt-0 min-w-0 flex-1">
          <TemplateSelector site={site!} onSaved={refetch} />
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={rollbackOpen}
        onOpenChange={setRollbackOpen}
        title="Roll back the live site"
        description={
          <>
            The live site switches to an earlier published version. Your draft content is not changed, and the
            next Publish creates a new version. Currently live:{" "}
            <span className="font-mono text-foreground">v{site.published_version}</span>.
          </>
        }
        destructive={false}
        confirmLabel={`Roll back to v${rollbackVersion || "?"}`}
        pendingLabel="Rolling back…"
        confirmDisabled={!/^[1-9]\d*$/.test(rollbackVersion) || Number(rollbackVersion) === site.published_version}
        onConfirm={handleRollback}
      >
        <FormField label="Version" htmlFor="rollback-version" hint="Versions are numbered from 1 in publish order.">
          <Input
            id="rollback-version"
            type="number"
            inputMode="numeric"
            min={1}
            value={rollbackVersion}
            onChange={(e) => setRollbackVersion(e.target.value)}
            className="w-32 font-mono"
          />
        </FormField>
      </ConfirmDialog>
    </TenantPage>
  )
}

export { SiteContentEditor }
