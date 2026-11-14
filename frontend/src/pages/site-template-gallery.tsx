/**
 * Full-page template gallery for a site (ADR-0003 UX rule: no side sheet for template
 * picking). Each card previews the template's real CSS (GET /api/templates/{slug}/css)
 * on sample block markup, in a sandboxed srcdoc iframe without scripts.
 */
import { useEffect, useState } from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"
import { Check, FileQuestion } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { EmptyState, LoadingState, Notice } from "@/components/page"
import { TierBadge } from "@/components/status-badges"
import { TenantPage, TenantPageHeader } from "@/components/tenant-page"
import { useTenantScope } from "@/context/tenant-scope-context"
import { useTenantRole } from "@/hooks/use-tenant-role"
import { useSites } from "@/hooks/use-sites"
import { templateCssUrl } from "@/lib/api-client"
import { fetchTemplates, getToken, type Template } from "@/lib/api"

const esc = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!)

/** Sample page in the template's chrome classes + block markup (base_layout / api/blocks). */
function sampleDoc(cssHref: string, siteName: string): string {
  const name = esc(siteName)
  return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><link rel="stylesheet" href="${esc(cssHref)}"></head>
<body><div class="site-wrapper"><header class="site-header"><h1 class="site-title">${name}</h1>
<nav class="site-nav"><ul><li><a href="#">About</a></li><li><a href="#">Blog</a></li><li><a href="#">Contact</a></li></ul></nav></header>
<main class="main-content"><section class="b-hero b-hero--center"><h2 class="b-hero__heading">${name}</h2>
<p class="b-hero__subheading">A short line about what you do and who it is for.</p><a class="b-button b-hero__cta" href="#">Get in touch</a></section>
<div class="b-columns b-columns--2"><div class="b-columns__col"><div class="b-richtext content"><h2>About us</h2><p>Tell visitors your story. Text, images, columns and buttons are all blocks you can rearrange.</p></div></div>
<div class="b-columns__col"><div class="b-richtext content"><h2>What we do</h2><ul><li>Services</li><li>Events</li><li>News</li></ul></div></div></div>
<section class="b-cta b-cta--primary"><h2 class="b-cta__heading">Ready to start?</h2><p class="b-cta__text">We reply within a day.</p><a class="b-button" href="#">Contact</a></section>
</main><footer class="site-footer">&copy; ${name}</footer></div></body></html>`
}

function TemplatePreview({ slug, siteName }: { slug: string; siteName: string }) {
  return (
    <div className="relative aspect-[4/3] overflow-hidden border-b bg-white">
      <iframe
        title={`Preview of the ${slug} template`}
        sandbox=""
        loading="lazy"
        tabIndex={-1}
        aria-hidden
        srcDoc={sampleDoc(templateCssUrl(slug), siteName)}
        className="pointer-events-none absolute top-0 left-0 h-[250%] w-[250%] origin-top-left scale-[0.4] border-0"
      />
    </div>
  )
}

export function SiteTemplateGallery() {
  const { siteId = "" } = useParams<{ siteId: string }>()
  const [params] = useSearchParams()
  const isNewSite = params.get("new") === "1"
  const navigate = useNavigate()
  const { api, basePath } = useTenantScope()
  const { canEdit } = useTenantRole()
  const { sites, loading, update } = useSites()
  const [templates, setTemplates] = useState<Template[] | null>(null)
  const [saving, setSaving] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const site = sites.find((s) => s.id === siteId)
  const doneTo = `${basePath}/sites/${siteId}/edit`

  useEffect(() => {
    let cancelled = false
    void getToken()
      .then((token) => fetchTemplates(api, token))
      .then((list) => !cancelled && setTemplates(list))
    return () => {
      cancelled = true
    }
  }, [api])

  const choose = async (slug: string) => {
    setSaving(slug)
    setError(null)
    const updated = await update(siteId, { template_id: slug })
    setSaving(null)
    if (updated) navigate(doneTo)
    else setError("Could not change the template. Try again.")
  }

  if (loading || templates === null)
    return (
      <TenantPage>
        <LoadingState label="Loading templates…" />
      </TenantPage>
    )
  if (!site)
    return (
      <TenantPage>
        <EmptyState
          icon={FileQuestion}
          title="Site not found"
          description="It may have been deleted, or the link is out of date."
          action={
            <Button asChild variant="outline">
              <Link to={`${basePath}/sites`}>Back to sites</Link>
            </Button>
          }
        />
      </TenantPage>
    )

  return (
    <TenantPage>
      <TenantPageHeader
        back={{ to: isNewSite ? `${basePath}/sites` : doneTo, label: isNewSite ? "Sites" : site.name }}
        eyebrow={site.name}
        title={isNewSite ? "Choose a template" : "Change template"}
        description="The template sets your site’s look: fonts, colours, header and footer. Your pages and posts are kept when you switch; publish again to apply it."
        actions={
          isNewSite && (
            <Button asChild variant="outline">
              <Link to={doneTo}>Decide later</Link>
            </Button>
          )
        }
      />
      {error && <Notice tone="danger">{error}</Notice>}
      {templates.length === 0 ? (
        <EmptyState icon={FileQuestion} title="No templates available" description="Ask your platform admin to add one." />
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {templates.map((t) => {
            const current = site.template_id === t.slug
            return (
              <article
                key={t.slug}
                className={`flex flex-col overflow-hidden rounded-lg border bg-card shadow-card ${
                  current ? "border-primary ring-2 ring-primary/25" : ""
                }`}
              >
                <TemplatePreview slug={t.forked_from || t.slug} siteName={site.name} />
                <div className="flex flex-1 flex-col gap-2 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="font-medium">{t.name}</h2>
                    {t.tier_required !== "FREE" && <TierBadge tier={t.tier_required} />}
                    {t.is_custom && <Badge mono>Custom</Badge>}
                    {current && (
                      <Badge tone="success">
                        <Check /> Current
                      </Badge>
                    )}
                  </div>
                  <p className="line-clamp-3 flex-1 text-sm text-muted-foreground">{t.description}</p>
                  {canEdit && (
                    <Button
                      variant={current ? "outline" : "default"}
                      disabled={current || saving !== null}
                      onClick={() => void choose(t.slug)}
                      aria-label={`Use the ${t.name} template`}
                    >
                      {saving === t.slug ? "Applying…" : current ? "In use" : "Use this template"}
                    </Button>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </TenantPage>
  )
}
