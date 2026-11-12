"use client"

import { useState, useCallback, useEffect, useMemo } from "react"
import { NativeSelect } from "@/components/ui/native-select"
import { Navigate } from "react-router-dom"
import { fetchAuthSession } from "aws-amplify/auth"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState, LoadingState, Page, PageHeader } from "@/components/page"
import { TierBadge } from "@/components/status-badges"
import {
  fetchAdminTemplates,
  createAdminTemplate,
  updateAdminTemplate,
  deleteAdminTemplate,
  type AdminTemplate,
} from "@/lib/api"
import { useAuth } from "@/hooks/use-auth"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { Layers, Pencil, Plus, Trash2 } from "lucide-react"

const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/
const TIERS = ["FREE", "PRO", "BUSINESS", "VIP"] as const

type SortBy = "name" | "slug" | "tier"

function slugError(slug: string): string | null {
  const s = slug.trim().toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")
  if (!s) return "Slug is required"
  if (s.length > 60) return "Slug must be at most 60 characters"
  if (!SLUG_PATTERN.test(s)) return "Slug must be lowercase letters, numbers, hyphens (e.g. my-template)"
  return null
}

function TemplatePreview({ template }: { template: AdminTemplate }) {
  const comp = template.components ?? {}
  const pages = (comp.pages as string[] | undefined) ?? []
  const sections = (comp.sections as Record<string, string[]> | undefined) ?? {}
  const sectionCount = Object.values(sections).flat().length
  return (
    <div className="rounded-md border bg-muted/50 p-3 text-sm">
      <p className="font-medium text-muted-foreground">Preview</p>
      <p className="mt-1">
        {pages.length} page(s): {pages.length ? pages.join(", ") : "—"}
      </p>
      <p className="mt-1 text-muted-foreground">
        {sectionCount} section(s) total
      </p>
      {Object.keys(comp).length > 0 && (
        <pre className="mt-2 max-h-32 overflow-auto rounded bg-background p-2 text-xs">
          {JSON.stringify(comp, null, 2)}
        </pre>
      )}
    </div>
  )
}

function EditTemplateForm({
  template,
  onSave,
  onCancel,
  saving,
}: {
  template: AdminTemplate
  onSave: (u: Partial<AdminTemplate>) => void
  onCancel: () => void
  saving: boolean
}) {
  const [name, setName] = useState(template.name)
  const [description, setDescription] = useState(template.description)
  const [tierRequired, setTierRequired] = useState(template.tier_required)
  const [error, setError] = useState<string | null>(null)
  return (
    <div className="mt-4 space-y-4">
      <div>
        <label className="text-sm font-medium">Name</label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mt-1.5"
        />
      </div>
      <div>
        <label className="text-sm font-medium">Description</label>
        <Input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="mt-1.5"
        />
      </div>
      <div>
        <label className="text-sm font-medium">Tier required</label>
        <NativeSelect
          className="mt-1.5"
          value={tierRequired}
          onChange={(e) => setTierRequired(e.target.value)}
        >
          {TIERS.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </NativeSelect>
      </div>
      <TemplatePreview template={{ ...template, name, description, tier_required: tierRequired }} />
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex gap-2">
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          disabled={saving || !name.trim()}
          onClick={() => {
            if (!name.trim()) {
              setError("Name is required")
              return
            }
            setError(null)
            onSave({ name, description, tier_required: tierRequired })
          }}
        >
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  )
}

function AdminTemplatesPage() {
  const { isAuthenticated, loading: authLoading } = useAuth()
  const { isSuperadmin, loading: superadminLoading } = useAdminTenants()
  const [templates, setTemplates] = useState<AdminTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [editTemplate, setEditTemplate] = useState<AdminTemplate | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createSlug, setCreateSlug] = useState("")
  const [createName, setCreateName] = useState("")
  const [createDesc, setCreateDesc] = useState("")
  const [createTier, setCreateTier] = useState("FREE")
  const [createError, setCreateError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [deleteSlug, setDeleteSlug] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<SortBy>("name")

  const load = useCallback(async () => {
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const list = await fetchAdminTemplates(token)
    setTemplates(list)
  }, [])

  useEffect(() => {
    void load().finally(() => setLoading(false))
  }, [load])

  const sortedTemplates = useMemo(() => {
    const copy = [...templates]
    if (sortBy === "name") copy.sort((a, b) => (a.name || a.slug).localeCompare(b.name || b.slug))
    else if (sortBy === "slug") copy.sort((a, b) => a.slug.localeCompare(b.slug))
    else if (sortBy === "tier") copy.sort((a, b) => a.tier_required.localeCompare(b.tier_required))
    return copy
  }, [templates, sortBy])

  if (authLoading || superadminLoading) {
    return (
      <Page>
        <LoadingState />
      </Page>
    )
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (!isSuperadmin) return <Navigate to="/" replace />

  const handleCreate = async () => {
    setCreateError(null)
    const slugNorm = createSlug.trim().toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")
    const err = slugError(slugNorm || createSlug)
    if (err) {
      setCreateError(err)
      return
    }
    if (!createName.trim()) {
      setCreateError("Name is required")
      return
    }
    setSaving(true)
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const result = await createAdminTemplate(token, {
      slug: slugNorm,
      name: createName.trim(),
      description: createDesc.trim(),
      tier_required: createTier,
      components: {},
    })
    setSaving(false)
    if (result.success) {
      setCreateOpen(false)
      setCreateSlug("")
      setCreateName("")
      setCreateDesc("")
      setCreateTier("FREE")
      void load()
    } else {
      setCreateError(result.error)
    }
  }

  const handleUpdate = async (slug: string, updates: Partial<AdminTemplate>) => {
    setSaving(true)
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const t = await updateAdminTemplate(token, slug, {
      name: updates.name,
      description: updates.description,
      tier_required: updates.tier_required,
      components: updates.components,
    })
    setSaving(false)
    if (t) {
      setEditTemplate(null)
      void load()
    }
  }

  const handleDeleteClick = (slug: string) => setDeleteSlug(slug)

  const handleDeleteConfirm = async () => {
    if (!deleteSlug) return
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const ok = await deleteAdminTemplate(token, deleteSlug)
    setDeleteSlug(null)
    if (ok) void load()
  }

  return (
    <Page>
      <PageHeader
        eyebrow="Platform"
        title="Templates"
        description="Site templates tenants can start from. The tier sets who can pick each one."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" />
            New template
          </Button>
        }
      />

      <Card className="gap-0 py-0">
        {loading ? (
          <LoadingState className="p-5" label="Loading templates…" />
        ) : templates.length === 0 ? (
          <EmptyState className="m-5" icon={Layers} title="No templates yet" />
        ) : (
          <>
            <div className="flex items-center justify-end gap-2 border-b px-5 py-3">
              <label htmlFor="template-sort" className="text-sm text-muted-foreground">
                Sort by
              </label>
              <NativeSelect
                id="template-sort"
                className="w-32"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortBy)}
              >
                <option value="name">Name</option>
                <option value="slug">Slug</option>
                <option value="tier">Tier</option>
              </NativeSelect>
            </div>
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Template</TableHead>
                  <TableHead>Tier</TableHead>
                  <TableHead className="hidden md:table-cell">Description</TableHead>
                  <TableHead className="text-right">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedTemplates.map((t) => (
                  <TableRow key={t.slug}>
                    <TableCell>
                      <span className="block font-medium">{t.name}</span>
                      <span className="block font-mono text-xs text-muted-foreground">{t.slug}</span>
                    </TableCell>
                    <TableCell>
                      <TierBadge tier={t.tier_required} />
                    </TableCell>
                    <TableCell className="hidden max-w-sm truncate text-muted-foreground md:table-cell">
                      {t.description || "—"}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                      <Button size="icon-sm" variant="ghost" onClick={() => setEditTemplate(t)} aria-label={`Edit ${t.name}`}>
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        onClick={() => handleDeleteClick(t.slug)}
                        aria-label={`Delete ${t.name}`}
                      >
                        <Trash2 className="size-4 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </>
        )}
      </Card>

      <Sheet open={createOpen} onOpenChange={setCreateOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Add template</SheetTitle>
          </SheetHeader>
          <div className="mt-4 space-y-4">
            <div>
              <label className="text-sm font-medium">Slug</label>
              <Input
                value={createSlug}
                onChange={(e) => {
                  const v = e.target.value.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "")
                  setCreateSlug(v.slice(0, 60))
                  setCreateError(null)
                }}
                placeholder="my-template"
                maxLength={60}
                className="mt-1.5"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Lowercase letters, numbers, hyphens. Max 60 chars.
              </p>
            </div>
            <div>
              <label className="text-sm font-medium">Name</label>
              <Input
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="My Template"
                className="mt-1.5"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Description</label>
              <Input
                value={createDesc}
                onChange={(e) => setCreateDesc(e.target.value)}
                placeholder="Optional"
                className="mt-1.5"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Tier required</label>
              <NativeSelect
                className="mt-1.5"
                value={createTier}
                onChange={(e) => setCreateTier(e.target.value)}
              >
                {TIERS.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </NativeSelect>
            </div>
            {createError && <p className="text-sm text-destructive">{createError}</p>}
            <Button
              onClick={handleCreate}
              disabled={saving || !createSlug.trim() || !createName.trim()}
            >
              {saving ? "Creating…" : "Create"}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      <Sheet open={!!editTemplate} onOpenChange={(o) => !o && setEditTemplate(null)}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Edit {editTemplate?.slug}</SheetTitle>
          </SheetHeader>
          {editTemplate && (
            <EditTemplateForm
              template={editTemplate}
              onSave={(updates) => {
                handleUpdate(editTemplate.slug, updates)
                setEditTemplate(null)
              }}
              onCancel={() => setEditTemplate(null)}
              saving={saving}
            />
          )}
        </SheetContent>
      </Sheet>

      <ConfirmDialog
        open={!!deleteSlug}
        onOpenChange={(o) => !o && setDeleteSlug(null)}
        title={`Delete template “${deleteSlug ?? ""}”?`}
        description="This permanently removes the template. Sites already created from it keep their content, but new sites can no longer use it."
        confirmLabel="Delete template"
        onConfirm={handleDeleteConfirm}
      />
    </Page>
  )
}

export { AdminTemplatesPage }
