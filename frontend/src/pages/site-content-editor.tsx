import { Link, useParams, Navigate } from "react-router-dom"
import { FileText, Newspaper, Calendar, Image } from "lucide-react"
import { useTenant } from "@/hooks/use-tenant"
import { useSites } from "@/hooks/use-sites"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

/**
 * Content editor shell (Task 2.90).
 * Layout with sidebar, page/post/event/media tabs.
 * Placeholder for per-module editors (2.91–2.94).
 */
function SiteContentEditor() {
  const { tenantSlug, tenantBasePath } = useTenant()
  const { siteId } = useParams<{ siteId: string }>()
  const { sites, loading } = useSites(tenantSlug)
  const base = tenantBasePath || `/${tenantSlug}`

  const site = siteId ? sites.find((s) => s.id === siteId) : null

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
        </TabsList>

        <TabsContent value="pages" className="mt-0 flex-1">
          <ContentPlaceholder
            title="Pages"
            description="Manage static pages (home, about, contact, etc.)."
            moduleRef="2.91"
          />
        </TabsContent>
        <TabsContent value="posts" className="mt-0 flex-1">
          <ContentPlaceholder
            title="Posts"
            description="Blog posts and updates. Draft vs Published."
            moduleRef="2.91"
          />
        </TabsContent>
        <TabsContent value="events" className="mt-0 flex-1">
          <ContentPlaceholder
            title="Events"
            description="Events, shows, tour dates. Date and venue."
            moduleRef="2.92"
          />
        </TabsContent>
        <TabsContent value="media" className="mt-0 flex-1">
          <ContentPlaceholder
            title="Media"
            description="Image gallery, uploads. Caption and reorder."
            moduleRef="2.93"
          />
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
