import { useState, useEffect } from "react"
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/ui/sheet"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantRole } from "@/hooks/use-tenant-role"
import { useSites } from "@/hooks/use-sites"
import { getToken } from "@/lib/api"
import { fetchTemplates, type Site, type Template } from "@/lib/api"

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
  const [status, setStatus] = useState(site?.status ?? "draft")
  const [templateId, setTemplateId] = useState(site?.template_id ?? "")
  const [saving, setSaving] = useState(false)
  const [templates, setTemplates] = useState<Template[]>([])

  useEffect(() => {
    async function loadTemplates() {
      if (!tenantSlug) return
      try {
        const token = await getToken()
        const list = await fetchTemplates(tenantSlug, token)
        setTemplates(list)
      } catch (e) {
        console.error("Failed to load templates", e)
      }
    }
    void loadTemplates()
  }, [tenantSlug])

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
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label htmlFor="site-name" className="text-sm font-medium">
          Name
        </label>
        <Input
          id="site-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="My site"
          required
          className="mt-1"
        />
      </div>
      <div>
        <label htmlFor="site-slug" className="text-sm font-medium">
          Slug (optional)
        </label>
        <Input
          id="site-slug"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          placeholder="my-site"
          className="mt-1"
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Lowercase letters, numbers, hyphens only
        </p>
      </div>
      <div>
        <label htmlFor="site-template" className="text-sm font-medium">
          Template (optional)
        </label>
        <select
          id="site-template"
          value={templateId}
          onChange={(e) => setTemplateId(e.target.value)}
          className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
        >
          <option value="">No template (Blank site)</option>
          {templates.map((t) => (
            <option key={t.slug} value={t.slug}>
              {t.name}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-muted-foreground">
          Templates are filtered by your tier. Pro+ sees more options.
        </p>
      </div>
      {site && (
        <div>
          <label htmlFor="site-status" className="text-sm font-medium">
            Status
          </label>
          <select
            id="site-status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
          >
            <option value="draft">Draft</option>
            <option value="published">Published</option>
          </select>
        </div>
      )}
      <SheetFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : site ? "Update" : "Create"}
        </Button>
      </SheetFooter>
    </form>
  )
}

function TenantSites() {
  const { tenantSlug } = useTenant()
  const { canEdit } = useTenantRole()
  const { sites, loading, error, create, update, remove } = useSites(tenantSlug)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editingSite, setEditingSite] = useState<Site | null>(null)

  const handleCreate = () => {
    setEditingSite(null)
    setSheetOpen(true)
  }

  const handleEdit = (site: Site) => {
    setEditingSite(site)
    setSheetOpen(true)
  }

  const handleDelete = async (site: Site) => {
    if (!confirm(`Delete "${site.name}"? This cannot be undone.`)) return
    await remove(site.id)
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
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Sites</h1>
          <p className="text-muted-foreground">
            Manage websites for {tenantSlug}
          </p>
        </div>
        {canEdit && (
          <Button onClick={handleCreate}>Add site</Button>
        )}
      </div>

      <Sheet
        open={sheetOpen}
        onOpenChange={(open) => {
          setSheetOpen(open)
          if (!open) setEditingSite(null)
        }}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{editingSite ? "Edit site" : "Add site"}</SheetTitle>
          </SheetHeader>
          <div className="mt-4">
            <SiteForm
              site={editingSite}
              onSubmit={handleSubmit}
              onClose={handleSheetClose}
            />
          </div>
        </SheetContent>
      </Sheet>

      {error && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Loading sites…</p>
          </CardContent>
        </Card>
      ) : sites.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Your sites</CardTitle>
            <CardDescription>Create and manage hosted websites</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              No sites yet. Create your first site to get started.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {sites.map((site) => (
            <Card key={site.id}>
              <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                <div>
                  <CardTitle className="text-base">{site.name}</CardTitle>
                  <CardDescription>{site.slug || site.id}</CardDescription>
                </div>
                {canEdit && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="size-8">
                        <MoreHorizontal className="size-4" />
                        <span className="sr-only">Actions</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleEdit(site)}>
                        <Pencil className="mr-2 size-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        variant="destructive"
                        onClick={() => handleDelete(site)}
                      >
                        <Trash2 className="mr-2 size-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      site.status === "published"
                        ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {site.status}
                  </span>
                  {site.template_id && (
                    <span className="inline-flex rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
                      Template: {site.template_id}
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

    </div>
  )
}

export { TenantSites }
