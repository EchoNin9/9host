import { useState, useEffect, useRef, useCallback } from "react"
import { ArrowUpRight, Check, Eye, FileEdit, Globe, Loader2, MoreHorizontal, Pencil, Plus, Trash2, X } from "lucide-react"
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { NativeSelect } from "@/components/ui/native-select"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState, FormField, LoadingState, Notice } from "@/components/page"
import { SiteStatusBadge } from "@/components/status-badges"
import { siteLiveUrl } from "@/lib/site-format"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
  SheetDescription,
} from "@/components/ui/sheet"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { FeatureGate } from "@/components/feature-gate"
import { Link, useSearchParams } from "react-router-dom"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantScope } from "@/context/tenant-scope-context"
import { useTenantRole } from "@/hooks/use-tenant-role"
import { useSites } from "@/hooks/use-sites"
import { SitePreview } from "@/components/site-preview"
import { TemplatePicker } from "@/components/template-picker"
import { getToken, validateSlug, fetchTemplates, forkTemplate, type Site, type Template } from "@/lib/api"
import { TenantPage, TenantPageHeader } from "@/components/tenant-page"

const SLUG_DEBOUNCE_MS = 400
const VALID_SLUG_RE = /^[a-z0-9-]*$/

function ForkTemplateSheet({
  open,
  onOpenChange,
  platformTemplates,
  onForked,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  platformTemplates: Template[]
  onForked: () => void
}) {
  const { api } = useTenantScope()
  const [templateSlug, setTemplateSlug] = useState("")
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFork = async () => {
    if (!templateSlug) return
    setError(null)
    setSaving(true)
    try {
      const token = await getToken()
      const result = await forkTemplate(api, token, {
        template_slug: templateSlug,
        name: name.trim() || undefined,
        slug: slug.trim() || undefined,
      })
      if (result) {
        onForked()
        onOpenChange(false)
        setTemplateSlug("")
        setName("")
        setSlug("")
      } else {
        setError("Fork failed. Pro+ tier required.")
      }
    } catch {
      setError("Fork failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent aria-describedby={undefined}>
        <SheetHeader>
          <SheetTitle>Fork template</SheetTitle>
        </SheetHeader>
        <div className="flex flex-col gap-5">
          <FormField label="Template" htmlFor="fork-template">
            <NativeSelect
              id="fork-template"
              value={templateSlug}
              onChange={(e) => setTemplateSlug(e.target.value)}
            >
              <option value="">Select…</option>
              {platformTemplates.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.name}
                </option>
              ))}
            </NativeSelect>
          </FormField>
          <FormField label="Name (optional)" htmlFor="fork-name">
            <Input
              id="fork-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My custom theme"
            />
          </FormField>
          <FormField label="Slug (optional)" htmlFor="fork-slug">
            <Input
              id="fork-slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
              placeholder="my-custom-theme"
              className="font-mono"
            />
          </FormField>
          {error && <Notice tone="danger">{error}</Notice>}
          <SheetFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={handleFork} disabled={saving || !templateSlug}>
              {saving ? "Forking…" : "Fork template"}
            </Button>
          </SheetFooter>
        </div>
      </SheetContent>
    </Sheet>
  )
}

function SiteForm({
  site,
  onSubmit,
  onClose,
}: {
  site: Site | null
  onSubmit: (body: { name: string; slug?: string; status?: string; template_id?: string | null }) => Promise<Site | null>
  onClose: () => void
}) {
  const [name, setName] = useState(site?.name ?? "")
  const [slug, setSlug] = useState(site?.slug ?? "")
  const { tenantSlug } = useTenant()
  const { api } = useTenantScope()
  const [status, setStatus] = useState(site?.status ?? "draft")
  const [templateId, setTemplateId] = useState(site?.template_id ?? "")
  const [saving, setSaving] = useState(false)
  const [templates, setTemplates] = useState<Template[]>([])
  type SlugStatus = "idle" | "checking" | "available" | "taken" | "invalid"
  const [slugStatus, setSlugStatus] = useState<SlugStatus>("idle")
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [forkOpen, setForkOpen] = useState(false)

  const loadTemplates = useCallback(async () => {
    if (!tenantSlug) return
    try {
      const token = await getToken()
      const list = await fetchTemplates(api, token)
      setTemplates(list)
    } catch (e) {
      console.error("Failed to load templates", e)
    }
  }, [tenantSlug])

  const checkSlug = useCallback(
    async (value: string) => {
      if (!tenantSlug || !value.trim()) {
        setSlugStatus("idle")
        return
      }
      const normalized = value.trim().toLowerCase()
      if (!VALID_SLUG_RE.test(normalized)) {
        setSlugStatus("invalid")
        return
      }
      setSlugStatus("checking")
      const token = await getToken()
      const result = await validateSlug(
        api,
        token,
        normalized,
        site?.id ?? null
      )
      if (result) {
        setSlugStatus(result.available ? "available" : "taken")
      } else {
        setSlugStatus("idle")
      }
    },
    [tenantSlug, site?.id]
  )

  useEffect(() => {
    void loadTemplates()
  }, [loadTemplates])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (!slug.trim()) {
      setSlugStatus("idle")
      return
    }
    debounceRef.current = setTimeout(() => {
      void checkSlug(slug)
    }, SLUG_DEBOUNCE_MS)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [slug, checkSlug])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    try {
      const body: { name: string; slug?: string; status?: string; template_id?: string | null } = {
        name: name.trim(),
        status,
      }
      if (slug.trim()) body.slug = slug.trim().toLowerCase()
      if (site) body.template_id = templateId || null
      else if (templateId) body.template_id = templateId
      const result = await onSubmit(body)
      if (result) onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <FormField label="Name" htmlFor="site-name">
        <Input
          id="site-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="My site"
          required
          autoFocus={!site}
        />
      </FormField>
      <div className="space-y-1.5">
        <Label htmlFor="site-slug">Slug</Label>
        <div className="relative">
          <Input
            id="site-slug"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="my-site"
            aria-invalid={slugStatus === "taken" || (slugStatus === "invalid" && !!slug.trim())}
            aria-describedby="site-slug-hint"
            className="pr-9 font-mono"
          />
          <span className="absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground">
            {slugStatus === "checking" && <Loader2 className="size-4 animate-spin" aria-hidden />}
            {slugStatus === "available" && <Check className="size-4 text-success" aria-hidden />}
            {(slugStatus === "taken" || (slugStatus === "invalid" && slug.trim())) && (
              <X className="size-4 text-destructive" aria-hidden />
            )}
          </span>
        </div>
        <p id="site-slug-hint" aria-live="polite" className="text-xs text-muted-foreground">
          {slugStatus === "available" && (
            <span className="text-success">
              Available — <span className="font-mono">{slug.trim().toLowerCase()}.echo9.net</span>
            </span>
          )}
          {slugStatus === "taken" && <span className="text-destructive">This slug is already taken</span>}
          {slugStatus === "invalid" && slug.trim() && (
            <span className="text-destructive">Use lowercase letters, numbers, and hyphens only</span>
          )}
          {(slugStatus === "idle" || slugStatus === "checking") &&
            "Optional. Sets the address, e.g. my-site.echo9.net. Lowercase letters, numbers, hyphens."}
        </p>
      </div>
      <div className="space-y-2">
        <Label>Template</Label>
        <TemplatePicker templates={templates} value={templateId} onChange={setTemplateId} />
        <p className="text-xs text-muted-foreground">
          Templates are filtered by your tier. You need one before you can publish.
        </p>
        <FeatureGate feature="custom_domains">
          <Button
            type="button"
            variant="link"
            className="h-auto p-0 text-xs"
            onClick={() => setForkOpen(true)}
          >
            Fork a template (Pro+)
          </Button>
        </FeatureGate>
      </div>
      <ForkTemplateSheet
        open={forkOpen}
        onOpenChange={setForkOpen}
        platformTemplates={templates.filter((t) => !t.is_custom)}
        onForked={loadTemplates}
      />
      {site && (
        <FormField
          label="Status"
          htmlFor="site-status"
          hint="Publishing from the content editor sets this to Published."
        >
          <NativeSelect id="site-status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="draft">Draft</option>
            <option value="published">Published</option>
          </NativeSelect>
        </FormField>
      )}
      <SheetFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={
            saving ||
            (slug.trim() !== "" &&
              (slugStatus === "taken" ||
                slugStatus === "invalid" ||
                slugStatus === "checking"))
          }
        >
          {saving ? "Saving…" : site ? "Save changes" : "Create site"}
        </Button>
      </SheetFooter>
    </form>
  )
}

function TenantSites() {
  const { tenantSlug, tenantBasePath } = useTenant()
  const base = tenantBasePath || `/${tenantSlug}`
  const { canEdit } = useTenantRole()
  const { sites, loading, error, create, update, remove } = useSites()
  const [searchParams, setSearchParams] = useSearchParams()
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editingSite, setEditingSite] = useState<Site | null>(null)
  const [previewSite, setPreviewSite] = useState<Site | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Site | null>(null)

  // ?new=1 (from the Overview "New site" button) opens the create sheet directly.
  const wantsNew = searchParams.get("new") === "1" && canEdit
  const isSheetOpen = sheetOpen || wantsNew
  const clearNew = () => {
    if (searchParams.has("new")) setSearchParams({}, { replace: true })
  }

  const handleCreate = () => {
    setEditingSite(null)
    setSheetOpen(true)
  }

  const handleEdit = (site: Site) => {
    setEditingSite(site)
    setSheetOpen(true)
  }

  const handleSubmit = async (body: {
    name: string
    slug?: string
    status?: string
    template_id?: string | null
  }) => {
    if (editingSite) {
      return update(editingSite.id, body)
    }
    return create(body)
  }

  const handleSheetClose = () => {
    setSheetOpen(false)
    setEditingSite(null)
    clearNew()
  }

  return (
    <TenantPage>
      <TenantPageHeader
        title="Sites"
        description="Each site publishes to its own echo9.net address. Edit content, preview drafts and publish from the content editor."
        actions={
          canEdit && (
            <Button onClick={handleCreate}>
              <Plus className="size-4" />
              New site
            </Button>
          )
        }
      />

      <Sheet
        open={isSheetOpen}
        onOpenChange={(open) => {
          setSheetOpen(open)
          if (!open) {
            setEditingSite(null)
            clearNew()
          }
        }}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{editingSite ? "Site settings" : "New site"}</SheetTitle>
            <SheetDescription>
              {editingSite ? (
                <span className="font-mono">{editingSite.slug || editingSite.id}</span>
              ) : (
                "Name it, pick an address and a template. You can change these later."
              )}
            </SheetDescription>
          </SheetHeader>
          <SiteForm
            key={editingSite?.id ?? "new"}
            site={editingSite}
            onSubmit={handleSubmit}
            onClose={handleSheetClose}
          />
        </SheetContent>
      </Sheet>

      {previewSite && (
        <SitePreview
          siteId={previewSite.id}
          siteName={previewSite.name}
          templateId={previewSite.template_id ?? null}
          open={!!previewSite}
          onOpenChange={(open) => !open && setPreviewSite(null)}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={`Delete “${deleteTarget?.name ?? ""}”?`}
        description="The site, its content and its published files are removed. Custom domains pointing at it stop working. This cannot be undone."
        confirmLabel="Delete site"
        onConfirm={async () => {
          if (deleteTarget) await remove(deleteTarget.id)
        }}
      />

      {error && <Notice tone="danger">{error}</Notice>}

      {loading ? (
        <LoadingState label="Loading sites…" />
      ) : sites.length === 0 ? (
        <EmptyState
          icon={Globe}
          title="No sites yet"
          description="Create a site from a template, add your pages, then publish it to the web."
          action={
            canEdit && (
              <Button onClick={handleCreate}>
                <Plus className="size-4" />
                Create your first site
              </Button>
            )
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {sites.map((site) => {
            const url = siteLiveUrl(site)
            const live = site.status === "published"
            return (
              <Card key={site.id} className="gap-4 transition-shadow hover:shadow-raised">
                <CardHeader className="flex flex-row items-start justify-between gap-3">
                  <div className="min-w-0 space-y-1">
                    <CardTitle className="truncate">{site.name}</CardTitle>
                    {url && live ? (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex max-w-full items-center gap-1 truncate font-mono text-xs text-muted-foreground hover:text-foreground"
                      >
                        <span className="truncate">{url.replace("https://", "")}</span>
                        <ArrowUpRight className="size-3 shrink-0" aria-hidden />
                        <span className="sr-only">(opens in a new tab)</span>
                      </a>
                    ) : (
                      <p className="truncate font-mono text-xs text-muted-foreground">
                        {site.slug ? `${site.slug}.echo9.net` : site.id}
                      </p>
                    )}
                  </div>
                  {canEdit && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon-sm" className="-mt-1 -mr-2 shrink-0">
                          <MoreHorizontal className="size-4" />
                          <span className="sr-only">More actions for {site.name}</span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => setPreviewSite(site)}>
                          <Eye className="size-4" />
                          Template preview
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => handleEdit(site)}>
                          <Pencil className="size-4" />
                          Site settings
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem variant="destructive" onSelect={() => setDeleteTarget(site)}>
                          <Trash2 className="size-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </CardHeader>
                <CardContent className="flex flex-wrap items-center gap-2">
                  <SiteStatusBadge site={site} />
                  {site.template_id ? (
                    <Badge mono>{site.template_id}</Badge>
                  ) : (
                    <Badge tone="warning">No template</Badge>
                  )}
                </CardContent>
                {canEdit && (
                  <CardFooter className="mt-auto gap-2 border-t pt-4 [.border-t]:pt-4">
                    <Button asChild size="sm" variant="outline" className="flex-1">
                      <Link to={`${base}/sites/${site.id}/edit`}>
                        <FileEdit className="size-4" />
                        Edit content
                      </Link>
                    </Button>
                  </CardFooter>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </TenantPage>
  )
}

export { TenantSites }
