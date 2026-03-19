import { Link, useParams, Navigate } from "react-router-dom"
import { useState } from "react"
import { FileText, Newspaper, Calendar, Image, Palette, ExternalLink } from "lucide-react"
import { useTenant } from "@/hooks/use-tenant"
import { useSites } from "@/hooks/use-sites"
import { getToken, fetchDraftPublish, fetchDraftToken } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { FeatureGate } from "@/components/feature-gate"
import { PostsEditor } from "@/components/content-editors/posts-editor"
import { EventsEditor } from "@/components/content-editors/events-editor"
import { MediaEditor } from "@/components/content-editors/media-editor"
import { BrandingEditor } from "@/components/content-editors/branding-editor"

/**
 * Content editor shell (Task 2.90).
 * Layout with sidebar, page/post/event/media/branding tabs.
 * Per-module editors (2.91–2.94).
 */
function SiteContentEditor() {
  const { tenantSlug, tenantBasePath } = useTenant()
  const { siteId } = useParams<{ siteId: string }>()
  const { sites, loading, refetch } = useSites(tenantSlug)
  const base = tenantBasePath || `/${tenantSlug}`
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)

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
      await fetchDraftPublish(tenantSlug, token, siteId)
      const data = await fetchDraftToken(tenantSlug, token, siteId)
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

  if (!tenantSlug || !siteId) {
    return <Navigate to={base ? `${base}/sites` : "/"} replace />
  }

  if (loading) {
    return (
      <div className="flex flex-1 flex-col gap-6 p-6">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    )
  }

  if (!site) {
    return (
      <div className="flex flex-1 flex-col gap-6 p-6">
        <p className="text-sm text-muted-foreground">Site not found.</p>
        <Button asChild variant="outline">
          <Link to={`${base}/sites`}>Back to sites</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link to={`${base}/sites`}>← Sites</Link>
            </Button>
          </div>
          <h1 className="mt-2 text-2xl font-semibold">{site.name}</h1>
          <p className="text-muted-foreground">
            Content editor — {site.slug || site.id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handlePreviewDraft}
            disabled={previewLoading || !site?.slug}
          >
            <ExternalLink className="mr-2 size-4" />
            {previewLoading ? "Preparing…" : "Preview draft"}
          </Button>
          {previewError && (
            <span className="text-sm text-destructive">{previewError}</span>
          )}
        </div>
      </div>

      <Tabs defaultValue="pages" orientation="vertical" className="flex flex-1 gap-6">
        <TabsList variant="line" className="h-fit w-48 shrink-0 flex-col items-stretch border-r border-border pr-4 bg-transparent p-0">
          <TabsTrigger value="pages" className="justify-start">
            <FileText className="mr-2 size-4" />
            Pages
          </TabsTrigger>
          <TabsTrigger value="posts" className="justify-start">
            <Newspaper className="mr-2 size-4" />
            Posts
          </TabsTrigger>
          <TabsTrigger value="events" className="justify-start">
            <Calendar className="mr-2 size-4" />
            Events
          </TabsTrigger>
          <TabsTrigger value="media" className="justify-start">
            <Image className="mr-2 size-4" />
            Media
          </TabsTrigger>
          <TabsTrigger value="branding" className="justify-start">
            <Palette className="mr-2 size-4" />
            Branding
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pages" className="mt-0 flex-1">
          <ContentPlaceholder
            title="Pages"
            description="Manage static pages (home, about, contact, etc.)."
            moduleRef="TBD"
          />
        </TabsContent>
        <TabsContent value="posts" className="mt-0 flex-1">
          <FeatureGate feature="updates_blog">
            <PostsEditor siteId={siteId!} />
          </FeatureGate>
        </TabsContent>
        <TabsContent value="events" className="mt-0 flex-1">
          <FeatureGate feature="events_shows">
            <EventsEditor siteId={siteId!} />
          </FeatureGate>
        </TabsContent>
        <TabsContent value="media" className="mt-0 flex-1">
          <FeatureGate feature="media_gallery">
            <MediaEditor siteId={siteId!} />
          </FeatureGate>
        </TabsContent>
        <TabsContent value="branding" className="mt-0 flex-1">
          <FeatureGate feature="branding">
            <BrandingEditor site={site!} onSaved={refetch} />
          </FeatureGate>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function ContentPlaceholder({
  title,
  description,
  moduleRef,
}: {
  title: string
  description: string
  moduleRef: string
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Placeholder for {title} editor. Task {moduleRef}.
        </p>
      </CardContent>
    </Card>
  )
}

export { SiteContentEditor }
