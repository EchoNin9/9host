"use client"

import { useState, useCallback, useEffect } from "react"
import { Navigate } from "react-router-dom"
import { fetchAuthSession } from "aws-amplify/auth"
import {
  Card,
  CardContent,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  fetchAdminTemplates,
  createAdminTemplate,
  updateAdminTemplate,
  deleteAdminTemplate,
  type AdminTemplate,
} from "@/lib/api"
import { useAuth } from "@/hooks/use-auth"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { Pencil, Trash2 } from "lucide-react"

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
  return (
    <div className="mt-4 space-y-4">
      <div>
        <label className="text-sm font-medium">Name</label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mt-1"
        />
      </div>
      <div>
        <label className="text-sm font-medium">Description</label>
        <Input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="mt-1"
        />
      </div>
      <div>
        <label className="text-sm font-medium">Tier required</label>
        <select
          value={tierRequired}
          onChange={(e) => setTierRequired(e.target.value)}
          className="mt-1 flex h-9 w-full rounded-md border border-input px-3 py-1 text-sm"
        >
          <option value="FREE">Free</option>
          <option value="PRO">Pro</option>
          <option value="BUSINESS">Business</option>
        </select>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          disabled={saving}
          onClick={() =>
            onSave({ name, description, tier_required: tierRequired })
          }
        >
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  )
}

function AdminTemplatesPage() {
  const { isAuthenticated, loading: authLoading } = useAuth()
  const { isSuperadmin } = useAdminTenants()
  const [templates, setTemplates] = useState<AdminTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [editTemplate, setEditTemplate] = useState<AdminTemplate | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createSlug, setCreateSlug] = useState("")
  const [createName, setCreateName] = useState("")
  const [createDesc, setCreateDesc] = useState("")
  const [createTier, setCreateTier] = useState("FREE")
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const list = await fetchAdminTemplates(token)
    setTemplates(list)
  }, [])

  useEffect(() => {
    void load().finally(() => setLoading(false))
  }, [load])

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="text-muted-foreground">Loading…</span>
      </div>
    )
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (!isSuperadmin) {
    return <Navigate to="/" replace />
  }

  const handleCreate = async () => {
    if (!createSlug.trim() || !createName.trim()) return
    setSaving(true)
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const t = await createAdminTemplate(token, {
      slug: createSlug.trim().toLowerCase().replace(/\s+/g, "-"),
      name: createName.trim(),
      description: createDesc.trim(),
      tier_required: createTier,
      components: {},
    })
    setSaving(false)
    if (t) {
      setCreateOpen(false)
      setCreateSlug("")
      setCreateName("")
      setCreateDesc("")
      setCreateTier("FREE")
      void load()
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

  const handleDelete = async (slug: string) => {
    if (!confirm(`Delete template "${slug}"?`)) return
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const ok = await deleteAdminTemplate(token, slug)
    if (ok) void load()
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Platform templates</h1>
          <p className="text-muted-foreground">
            Manage site templates. Tier-gated for tenant site creation.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>Add template</Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 text-sm text-muted-foreground">Loading…</div>
          ) : templates.length === 0 ? (
            <div className="p-6 text-sm text-muted-foreground">No templates yet.</div>
          ) : (
            <div className="divide-y">
              {templates.map((t) => (
                <div
                  key={t.slug}
                  className="flex items-center justify-between p-4"
                >
                  <div>
                    <span className="font-medium">{t.name}</span>
                    <span className="ml-2 text-sm text-muted-foreground">
                      ({t.slug}) · {t.tier_required}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditTemplate(t)}
                    >
                      <Pencil className="size-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDelete(t.slug)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
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
                onChange={(e) => setCreateSlug(e.target.value)}
                placeholder="my-template"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Name</label>
              <Input
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="My Template"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Description</label>
              <Input
                value={createDesc}
                onChange={(e) => setCreateDesc(e.target.value)}
                placeholder="Optional"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Tier required</label>
              <select
                value={createTier}
                onChange={(e) => setCreateTier(e.target.value)}
                className="mt-1 flex h-9 w-full rounded-md border border-input px-3 py-1 text-sm"
              >
                <option value="FREE">Free</option>
                <option value="PRO">Pro</option>
                <option value="BUSINESS">Business</option>
              </select>
            </div>
            <Button onClick={handleCreate} disabled={saving || !createSlug.trim() || !createName.trim()}>
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
    </div>
  )
}

export { AdminTemplatesPage }
