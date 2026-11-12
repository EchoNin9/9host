import { Link } from "react-router-dom"
import { ArrowUpRight, Check, Globe, Plus } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState, LoadingState } from "@/components/page"
import { TenantPage, TenantPageHeader } from "@/components/tenant-page"
import { SiteStatusBadge, TierBadge } from "@/components/status-badges"
import { siteLiveUrl, tierLabel } from "@/lib/site-format"
import { useTenant } from "@/hooks/use-tenant"
import { useTenants } from "@/hooks/use-tenants"
import { useTenantRole } from "@/hooks/use-tenant-role"
import { useSites } from "@/hooks/use-sites"
import { useDomains } from "@/hooks/use-domains"
import { useTenantMetadata } from "@/hooks/use-tenant-metadata"
import { cn } from "@/lib/utils"

function Stat({ label, value, detail, to }: { label: string; value: number | string; detail?: string; to?: string }) {
  const body = (
    <>
      <p className="eyebrow">{label}</p>
      <p className="tabular mt-2 text-3xl font-light tracking-tight text-foreground">{value}</p>
      {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
    </>
  )
  return to ? (
    <Link to={to} className="rounded-lg border bg-card p-4 shadow-card transition-colors hover:border-input hover:bg-accent/40">
      {body}
    </Link>
  ) : (
    <div className="rounded-lg border bg-card p-4 shadow-card">{body}</div>
  )
}

function Step({ done, title, children }: { done: boolean; title: string; children?: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span
        className={cn(
          "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border text-[0.6875rem]",
          done ? "border-success bg-success text-background" : "border-input bg-card"
        )}
        aria-hidden
      >
        {done && <Check className="size-3" strokeWidth={3} />}
      </span>
      <div className="min-w-0 text-sm">
        <p className={cn("font-medium", done && "text-muted-foreground line-through decoration-muted-foreground/40")}>
          {title}
          <span className="sr-only">{done ? " (done)" : " (to do)"}</span>
        </p>
        {!done && children && <div className="mt-0.5 text-muted-foreground">{children}</div>}
      </div>
    </li>
  )
}

function TenantDashboard() {
  const { tenantSlug, tenantBasePath } = useTenant()
  const base = tenantBasePath || `/${tenantSlug}`
  const { tenants } = useTenants()
  const { tenant } = useTenantMetadata()
  const { canEdit } = useTenantRole()
  const { sites, loading: sitesLoading } = useSites()
  const { domains } = useDomains()

  const name = tenant?.name || tenants.find((t) => t.slug === tenantSlug)?.name || tenantSlug
  const live = sites.filter((s) => s.status === "published")
  const activeDomains = domains.filter((d) => d.status === "ACTIVE").length
  const hasTemplate = sites.some((s) => !!s.template_id)
  const showChecklist = !sitesLoading && live.length === 0

  return (
    <TenantPage>
      <TenantPageHeader
        eyebrow="Overview"
        title={name}
        meta={<TierBadge tier={tenant?.tier} />}
        description={
          <>
            Default address <span className="font-mono text-foreground">{tenantSlug}.echo9.net</span>
          </>
        }
        actions={
          canEdit && (
            <Button asChild>
              <Link to={`${base}/sites?new=1`}>
                <Plus className="size-4" />
                New site
              </Link>
            </Button>
          )
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Sites" value={sites.length} detail={`${live.length} live`} to={`${base}/sites`} />
        <Stat label="Live" value={live.length} detail="published on echo9.net" to={`${base}/sites`} />
        <Stat
          label="Custom domains"
          value={domains.length}
          detail={domains.length ? `${activeDomains} active` : "none connected"}
          to={`${base}/domains`}
        />
        <Stat label="Plan" value={tierLabel(tenant?.tier)} detail="tier" to={`${base}/modules`} />
      </div>

      <div className={cn("grid gap-6", showChecklist && "lg:grid-cols-[1fr_20rem]")}>
        <Card className="gap-0 py-0">
          <CardHeader className="flex flex-row items-center justify-between border-b py-4">
            <div>
              <CardTitle>Sites</CardTitle>
              <CardDescription>Most recently created first.</CardDescription>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link to={`${base}/sites`}>
                View all
                <ArrowUpRight className="size-4" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="px-0">
            {sitesLoading ? (
              <LoadingState className="p-5" rows={2} label="Loading sites…" />
            ) : sites.length === 0 ? (
              <EmptyState
                className="m-5"
                icon={Globe}
                title="No sites yet"
                description="Create a site from a template, add pages, then publish it to the web."
                action={
                  canEdit && (
                    <Button asChild size="sm">
                      <Link to={`${base}/sites?new=1`}>Create a site</Link>
                    </Button>
                  )
                }
              />
            ) : (
              <ul className="divide-y">
                {[...sites]
                  .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
                  .slice(0, 6)
                  .map((site) => {
                    const url = siteLiveUrl(site)
                    return (
                      <li key={site.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-medium">{site.name}</p>
                          {url && site.status === "published" ? (
                            <a
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="truncate font-mono text-xs text-muted-foreground hover:text-foreground"
                            >
                              {url.replace("https://", "")}
                            </a>
                          ) : (
                            <p className="truncate font-mono text-xs text-muted-foreground">{site.slug || site.id}</p>
                          )}
                        </div>
                        <SiteStatusBadge site={site} />
                        {canEdit && (
                          <Button asChild variant="outline" size="sm">
                            <Link to={`${base}/sites/${site.id}/edit`}>Edit content</Link>
                          </Button>
                        )}
                      </li>
                    )
                  })}
              </ul>
            )}
          </CardContent>
        </Card>

        {showChecklist && (
          <Card>
            <CardHeader>
              <CardTitle>Get your first site live</CardTitle>
              <CardDescription>Four steps, about ten minutes.</CardDescription>
            </CardHeader>
            <CardContent>
              <ol className="space-y-4">
                <Step done={sites.length > 0} title="Create a site">
                  <Link to={`${base}/sites?new=1`} className="text-primary underline-offset-4 hover:underline">
                    New site
                  </Link>{" "}
                  — name it and pick a slug.
                </Step>
                <Step done={hasTemplate} title="Choose a template">
                  Pick one when creating the site, or in the editor’s Templates tab.
                </Step>
                <Step done={live.length > 0} title="Add content and publish">
                  Open the content editor, add pages, then press Publish.
                </Step>
                <Step done={domains.length > 0} title="Connect a custom domain">
                  Optional. Point your own domain at a published site.
                </Step>
              </ol>
            </CardContent>
          </Card>
        )}
      </div>
    </TenantPage>
  )
}

export { TenantDashboard }
