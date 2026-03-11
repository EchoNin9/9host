"use client"

import { useState } from "react"
import { Link, Navigate, useNavigate } from "react-router-dom"
import { fetchAuthSession } from "aws-amplify/auth"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
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
import { useAuth } from "@/hooks/use-auth"
import { useImpersonation } from "@/hooks/use-impersonation"
import {
  fetchAdminTenant,
  patchAdminTenant,
  type AdminTenantDetail,
} from "@/lib/api"
import { UserCog, Pencil } from "lucide-react"

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

function SuperadminPage() {
  const { isAuthenticated, loading: authLoading } = useAuth()
  const { tenants, loading, isSuperadmin, refetch } = useAdminTenants()
  const { setImpersonate } = useImpersonation()
  const navigate = useNavigate()
  const [editSlug, setEditSlug] = useState<string | null>(null)
  const [editTenant, setEditTenant] = useState<AdminTenantDetail | null>(null)

  const handleEdit = async (slug: string) => {
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const t = await fetchAdminTenant(token, slug)
    if (t) {
      setEditTenant(t)
      setEditSlug(slug)
    }
  }

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="text-muted-foreground">Loading…</span>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (!loading && !isSuperadmin) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Access denied</CardTitle>
            <CardDescription>
              Superadmin access required. You do not have permission to view this
              page.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="secondary">
              <Link to="/">Back to platform</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const handleImpersonate = (slug: string) => {
    setImpersonate(slug)
    navigate(`/${slug}`)
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-8">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <div className="flex items-center gap-2">
            <UserCog className="size-6" />
            <CardTitle>Superadmin — All Tenants</CardTitle>
          </div>
          <CardDescription>
            Platform admin view. Impersonate a tenant to act as them.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading tenants…</p>
          ) : tenants.length === 0 ? (
            <p className="text-sm text-muted-foreground">No tenants yet.</p>
          ) : (
            <ul className="space-y-2">
              {tenants.map((t) => (
                <li
                  key={t.slug}
                  className="flex items-center justify-between rounded-lg border p-3"
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
                      <Pencil className="size-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => handleImpersonate(t.slug)}
                    >
                      Impersonate
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-4 flex gap-4">
            <Button asChild variant="link" className="p-0">
              <Link to="/admin/templates">Templates</Link>
            </Button>
            <Button asChild variant="link" className="p-0">
              <Link to="/">← Back to platform</Link>
            </Button>
          </p>
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
    </div>
  )
}

export { SuperadminPage }
