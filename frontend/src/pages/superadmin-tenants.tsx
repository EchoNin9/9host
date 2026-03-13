"use client"

import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
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
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Input } from "@/components/ui/input"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { useImpersonation } from "@/hooks/use-impersonation"
import {
  createAdminTenant,
  deleteAdminTenant,
  getToken,
} from "@/lib/api"
import { Plus, Trash2 } from "lucide-react"

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
    const token = await getToken()
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
          <option value="VIP">VIP</option>
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
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteSlug, setDeleteSlug] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async () => {
    if (!deleteSlug) return
    setDeleting(true)
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const ok = await deleteAdminTenant(token, deleteSlug)
    setDeleting(false)
    if (ok) {
      setDeleteSlug(null)
      void refetch()
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
                    <Button size="sm" variant="outline" asChild>
                      <Link to={`/admin/tenants/${t.slug}`}>Administer</Link>
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => handleImpersonate(t.slug)}
                    >
                      Impersonate
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => setDeleteSlug(t.slug)}
                    >
                      <Trash2 className="mr-2 size-4" />
                      Delete
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

      <AlertDialog open={!!deleteSlug} onOpenChange={(o) => !o && !deleting && setDeleteSlug(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete tenant "{deleteSlug}"?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the tenant and all its sites, domains, users, and settings. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <Button variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? "Deleting…" : "Delete tenant"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

export { SuperadminTenantsPage }
