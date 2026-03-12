"use client"

import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { fetchAuthSession } from "aws-amplify/auth"
import {
  Card,
  CardContent,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Input } from "@/components/ui/input"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { useImpersonation } from "@/hooks/use-impersonation"
import {
  fetchAdminTenant,
  patchAdminTenant,
  createAdminTenant,
  type AdminTenantDetail,
} from "@/lib/api"
import { Pencil, Plus } from "lucide-react"

const FEATURE_KEYS = ["custom_domains", "advanced_analytics"] as const

function TenantEditSheet({
  tenant,
  onClose,
  onSaved,
}: {
  tenant: AdminTenantDetail
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState(tenant.name)
  const [tier, setTier] = useState(tenant.tier)
  const [moduleOverrides, setModuleOverrides] = useState<Record<string, boolean>>(
    tenant.module_overrides ?? { custom_domains: false, advanced_analytics: false }
  )
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const result = await patchAdminTenant(token, tenant.slug, {
      name,
      tier,
      module_overrides: moduleOverrides,
    })
    setSaving(false)
    if (result) {
      onSaved()
      onClose()
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium">Name</label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mt-1"
        />
      </div>
      <div>
        <label className="text-sm font-medium">Tier</label>
        <select
          value={tier}
          onChange={(e) => setTier(e.target.value)}
          className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
        >
          <option value="FREE">Free</option>
          <option value="PRO">Pro</option>
          <option value="BUSINESS">Business</option>
        </select>
      </div>
      <div>
        <label className="text-sm font-medium">Module overrides</label>
        <p className="text-xs text-muted-foreground mb-2">
          Override tier-based features (e.g. Free + custom_domains)
        </p>
        <div className="space-y-2">
          {FEATURE_KEYS.map((key) => (
            <label key={key} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={moduleOverrides[key] ?? false}
                onChange={(e) =>
                  setModuleOverrides((m) => ({ ...m, [key]: e.target.checked }))
                }
                className="h-4 w-4 rounded"
              />
              <span className="text-sm capitalize">{key.replace("_", " ")}</span>
            </label>
          ))}
        </div>
      </div>
      <div className="flex gap-2">
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  )
}

function CreateTenantSheet({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: () => void
}) {
  const [slug, setSlug] = useState("")
  const [name, setName] = useState("")
  const [tier, setTier] = useState("FREE")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSlugChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value.toLowerCase().replace(/\s/g, "-").replace(/[^a-z0-9-]/g, "")
    setSlug(v.slice(0, 60))
  }

  const handleCreate = async () => {
    setError(null)
    const s = slug.trim()
    if (!s) {
      setError("Slug is required")
      return
    }
    if (s.length > 60) {
      setError("Slug must be at most 60 characters")
      return
    }
    if (!/^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/.test(s)) {
      setError("Slug must be lowercase alphanumeric and hyphen (e.g. acme-corp)")
      return
    }
    setSaving(true)
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const result = await createAdminTenant(token, {
      slug: s,
      name: name.trim() || s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      tier,
    })
    setSaving(false)
    if (result) {
      onCreated()
      onClose()
    } else {
      setError("Failed to create tenant")
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm font-medium">Slug</label>
        <Input
          value={slug}
          onChange={handleSlugChange}
          placeholder="acme-corp"
          maxLength={60}
          className="mt-1"
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Lowercase letters, numbers, hyphens. Max 60 chars.
        </p>
      </div>
      <div>
        <label className="text-sm font-medium">Display name</label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Acme Corp"
          className="mt-1"
        />
      </div>
      <div>
        <label className="text-sm font-medium">Tier</label>
        <select
          value={tier}
          onChange={(e) => setTier(e.target.value)}
          className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
        >
          <option value="FREE">Free</option>
          <option value="PRO">Pro</option>
          <option value="BUSINESS">Business</option>
        </select>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex gap-2">
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={handleCreate} disabled={saving}>
          {saving ? "Creating…" : "Create tenant"}
        </Button>
      </div>
    </div>
  )
}

function SuperadminTenantsPage() {
  const { tenants, loading, refetch } = useAdminTenants()
  const { setImpersonate } = useImpersonation()
  const navigate = useNavigate()
  const [editSlug, setEditSlug] = useState<string | null>(null)
  const [editTenant, setEditTenant] = useState<AdminTenantDetail | null>(null)
  const [createOpen, setCreateOpen] = useState(false)

  const handleEdit = async (slug: string) => {
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const t = await fetchAdminTenant(token, slug)
    if (t) {
      setEditTenant(t)
      setEditSlug(slug)
    }
  }

  const handleImpersonate = (slug: string) => {
    setImpersonate(slug)
    navigate(`/${slug}`)
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Tenants</h1>
          <p className="text-muted-foreground">
            Manage all tenants on the platform.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 size-4" />
          Add Tenant
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 text-sm text-muted-foreground">Loading tenants…</div>
          ) : tenants.length === 0 ? (
            <div className="p-6 text-sm text-muted-foreground">No tenants yet.</div>
          ) : (
            <div className="divide-y">
              {tenants.map((t) => (
                <div
                  key={t.slug}
                  className="flex items-center justify-between p-4"
                >
                  <div>
                    <span className="font-medium">{t.name || t.slug}</span>
                    <span className="ml-2 text-sm text-muted-foreground">
                      ({t.slug}) · {t.tier}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleEdit(t.slug)}
                    >
                      <Pencil className="mr-2 size-4" />
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => handleImpersonate(t.slug)}
                    >
                      Impersonate
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Sheet open={!!editSlug} onOpenChange={(o) => !o && (setEditSlug(null), setEditTenant(null))}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Edit tenant {editSlug}</SheetTitle>
          </SheetHeader>
          <div className="mt-4">
            {editTenant && (
              <TenantEditSheet
                tenant={editTenant}
                onClose={() => (setEditSlug(null), setEditTenant(null))}
                onSaved={() => void refetch()}
              />
            )}
          </div>
        </SheetContent>
      </Sheet>

      <Sheet open={createOpen} onOpenChange={setCreateOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Add tenant</SheetTitle>
          </SheetHeader>
          <div className="mt-4">
            <CreateTenantSheet
              onClose={() => setCreateOpen(false)}
              onCreated={() => void refetch()}
            />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}

export { SuperadminTenantsPage }
