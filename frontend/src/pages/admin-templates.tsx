/**
 * Superadmin template list (T-32b, ADR-0003 §5). Editing is the full-page
 * /admin/templates/:slug/edit route; "New template" is an inline form (no side sheet).
 * The route sits inside SuperadminLayout, which already requires a superadmin.
 */
import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Layers, Plus, Trash2 } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { NativeSelect } from "@/components/ui/native-select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState, FormField, LoadingState, Notice, Page, PageHeader } from "@/components/page"
import { TierBadge } from "@/components/status-badges"
import { createAdminTemplate, deleteAdminTemplate, fetchAdminTemplates, type AdminTemplate } from "@/lib/api"
import { BASE_RENDERERS, SLUG_RE, TIERS } from "@/lib/template-tokens"

const editPath = (slug: string) => `/admin/templates/${encodeURIComponent(slug)}/edit`
const normalizeSlug = (v: string) => v.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "").slice(0, 60)

function VersionSummary({ t }: { t: Pick<AdminTemplate, "latest_version" | "published_version"> }) {
  if (!t.latest_version) return <span className="text-muted-foreground">No versions yet</span>
  return (
    <span className="tabular-nums">
      {t.published_version ? `Published v${t.published_version}` : "Not published"}
      <span className="text-muted-foreground"> · latest v{t.latest_version}</span>
    </span>
  )
}

function NewTemplateForm({ onCancel }: { onCancel: () => void }) {
  const navigate = useNavigate()
  const [slug, setSlug] = useState("")
  const [name, setName] = useState("")
  const [tier, setTier] = useState("FREE")
  const [base, setBase] = useState<string>("business-generic")
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const slugErr = !slug ? "Enter a slug" : !SLUG_RE.test(slug) ? "Lowercase letters, numbers and hyphens (e.g. my-template)" : null
    if (slugErr) return setError(slugErr)
    if (!name.trim()) return setError("Enter a name")
    setSaving(true)
    const r = await createAdminTemplate({ slug, name: name.trim(), tier_required: tier, base_renderer: base })
    setSaving(false)
    if (r.ok) navigate(editPath(r.data.slug))
    else setError(r.error)
  }

  return (
    <Card className="p-5">
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="New template">
        <FormField label="Slug" htmlFor="new-template-slug" hint="Lowercase letters, numbers, hyphens">
          <Input
            id="new-template-slug"
            value={slug}
            placeholder="my-template"
            onChange={(e) => {
              setSlug(normalizeSlug(e.target.value))
              setError(null)
            }}
          />
        </FormField>
        <FormField label="Name" htmlFor="new-template-name">
          <Input id="new-template-name" value={name} placeholder="My template" onChange={(e) => setName(e.target.value)} />
        </FormField>
        <FormField label="Tier required" htmlFor="new-template-tier">
          <NativeSelect id="new-template-tier" value={tier} onChange={(e) => setTier(e.target.value)}>
            {TIERS.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </NativeSelect>
        </FormField>
        <FormField label="Base design" htmlFor="new-template-base">
          <NativeSelect id="new-template-base" value={base} onChange={(e) => setBase(e.target.value)}>
            {BASE_RENDERERS.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </NativeSelect>
        </FormField>
        {error && <p className="text-sm text-destructive sm:col-span-2 lg:col-span-4">{error}</p>}
        <div className="flex gap-2 sm:col-span-2 lg:col-span-4">
          <Button type="submit" disabled={saving}>{saving ? "Creating…" : "Create and edit"}</Button>
          <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  )
}

function AdminTemplatesPage() {
  const [templates, setTemplates] = useState<AdminTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [deleteSlug, setDeleteSlug] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const [reload, setReload] = useState(0)

  useEffect(() => {
    let cancelled = false
    void fetchAdminTemplates().then((r) => {
      if (cancelled) return
      if (r.ok) setTemplates(r.data?.templates ?? [])
      else setLoadError(r.error)
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [reload])

  const sorted = useMemo(() => [...templates].sort((a, b) => (a.name || a.slug).localeCompare(b.name || b.slug)), [templates])

  return (
    <Page>
      <PageHeader
        eyebrow="Platform"
        title="Templates"
        description="Site templates tenants can start from. The tier sets who can pick each one."
        actions={
          !creating && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="size-4" />
              New template
            </Button>
          )
        }
      />
      {creating && <NewTemplateForm onCancel={() => setCreating(false)} />}
      {loadError && <Notice tone="danger" title="Could not load templates">{loadError}</Notice>}
      {deleteError && (
        <Notice tone="danger" title="Template not deleted" action={<Button variant="ghost" size="sm" onClick={() => setDeleteError(null)}>Dismiss</Button>}>
          {deleteError}
        </Notice>
      )}

      <Card className="gap-0 py-0">
        {loading ? (
          <LoadingState className="p-5" label="Loading templates…" />
        ) : templates.length === 0 ? (
          <EmptyState className="m-5" icon={Layers} title="No templates yet" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Template</TableHead>
                <TableHead className="hidden md:table-cell">Base design</TableHead>
                <TableHead>Tier</TableHead>
                <TableHead>Versions</TableHead>
                <TableHead className="text-right">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map((t) => (
                <TableRow key={t.slug}>
                  <TableCell>
                    <span className="flex items-center gap-2">
                      <Link to={editPath(t.slug)} className="font-medium hover:underline">{t.name}</Link>
                      {t.deprecated && <Badge tone="warning">Deprecated</Badge>}
                    </span>
                    <span className="block font-mono text-xs text-muted-foreground">{t.slug}</span>
                  </TableCell>
                  <TableCell className="hidden font-mono text-xs md:table-cell">{t.base_renderer || "—"}</TableCell>
                  <TableCell>
                    <TierBadge tier={t.tier_required} />
                  </TableCell>
                  <TableCell className="text-sm">
                    <VersionSummary t={t} />
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap">
                    <Button asChild size="sm" variant="outline">
                      <Link to={editPath(t.slug)} aria-label={`Edit ${t.name}`}>Edit</Link>
                    </Button>
                    <Button size="icon-sm" variant="ghost" onClick={() => setDeleteSlug(t.slug)} aria-label={`Delete ${t.name}`}>
                      <Trash2 className="size-4 text-destructive" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <ConfirmDialog
        open={!!deleteSlug}
        onOpenChange={(o) => !o && setDeleteSlug(null)}
        title={`Delete template “${deleteSlug ?? ""}”?`}
        description="This permanently removes the template. A template that sites still use cannot be deleted; deprecate it instead."
        confirmLabel="Delete template"
        onConfirm={async () => {
          if (!deleteSlug) return
          const r = await deleteAdminTemplate(deleteSlug)
          if (r.ok) setReload((n) => n + 1)
          else setDeleteError(r.error)
        }}
      />
    </Page>
  )
}

export { AdminTemplatesPage }
