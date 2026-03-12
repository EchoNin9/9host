"use client"

import { useState, useCallback, useEffect } from "react"
import { Link, Navigate, useNavigate, useParams } from "react-router-dom"
import { fetchAuthSession } from "aws-amplify/auth"
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
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { useImpersonation } from "@/hooks/use-impersonation"
import {
  fetchAdminTenant,
  deleteAdminTenant,
  putAdminTenantSettings,
  fetchAdminDomains,
  createAdminDomain,
  deleteAdminDomain,
  fetchAdminSites,
  createAdminSite,
  updateAdminSite,
  deleteAdminSite,
  fetchAdminTenantUsers,
  createAdminUser,
  updateAdminUser,
  deleteAdminUser,
  fetchAdminUserPermissions,
  updateAdminUserPermissions,
  fetchAdminTemplates,
  type AdminTenantDetail,
  type Domain,
  type Site,
  type TenantUser,
  type ModulePermissions,
  MODULE_KEYS,
} from "@/lib/api"
import { ArrowLeft, Globe, GlobeLock, Settings, Trash2, Users } from "lucide-react"

const FEATURE_KEYS = ["custom_domains", "advanced_analytics"] as const

type TabId = "domains" | "sites" | "users" | "settings"

function AdministerTenantPage() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const { isSuperadmin, loading: superadminLoading } = useAdminTenants()
  const { setImpersonate } = useImpersonation()
  const [tenant, setTenant] = useState<AdminTenantDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<TabId>("domains")
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const loadTenant = useCallback(async () => {
    if (!slug) return
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const t = await fetchAdminTenant(token, slug)
    setTenant(t)
  }, [slug])

  useEffect(() => {
    if (!slug) {
      setLoading(false)
      return
    }
    void loadTenant().finally(() => setLoading(false))
  }, [slug, loadTenant])

  const handleDelete = async () => {
    if (!slug) return
    setDeleting(true)
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const ok = await deleteAdminTenant(token, slug)
    setDeleting(false)
    if (ok) {
      setDeleteOpen(false)
      navigate("/admin/tenants")
    }
  }

  if (superadminLoading) return <div className="flex min-h-screen items-center justify-center">Loading…</div>
  if (!isSuperadmin) return <Navigate to="/" replace />
  if (!slug) return <Navigate to="/admin/tenants" replace />
  if (loading) return <div className="flex min-h-screen items-center justify-center">Loading…</div>
  if (!tenant) return <div className="p-6">Tenant not found.</div>

  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: "domains", label: "Domains", icon: <GlobeLock className="size-4" /> },
    { id: "sites", label: "Sites", icon: <Globe className="size-4" /> },
    { id: "users", label: "Users", icon: <Users className="size-4" /> },
    { id: "settings", label: "Settings", icon: <Settings className="size-4" /> },
  ]

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/admin/tenants"
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back to tenants
          </Link>
          <div>
            <h1 className="text-2xl font-semibold">{tenant.name || tenant.slug}</h1>
            <p className="text-muted-foreground">
              {tenant.slug} · {tenant.tier}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => { setImpersonate(slug); navigate(`/${slug}`) }}>
            Impersonate
          </Button>
          <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="mr-2 size-4" />
            Delete tenant
          </Button>
        </div>
      </div>

      <div className="flex gap-2 border-b">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {tab === "domains" && (
        <AdminDomainsTab tenantSlug={slug} />
      )}
      {tab === "sites" && (
        <AdminSitesTab tenantSlug={slug} />
      )}
      {tab === "users" && (
        <AdminUsersTab tenantSlug={slug} />
      )}
      {tab === "settings" && (
        <AdminSettingsTab tenant={tenant} onSaved={loadTenant} />
      )}

      <AlertDialog open={deleteOpen} onOpenChange={(o) => !o && !deleting && setDeleteOpen(false)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete tenant &quot;{slug}&quot;?</AlertDialogTitle>
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

function AdminDomainsTab({ tenantSlug }: { tenantSlug: string }) {
  const [domains, setDomains] = useState<Domain[]>([])
  const [sites, setSites] = useState<Site[]>([])
  const [loading, setLoading] = useState(true)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [addDomain, setAddDomain] = useState("")
  const [addSiteId, setAddSiteId] = useState("")
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const [d, s] = await Promise.all([
      fetchAdminDomains(token, tenantSlug),
      fetchAdminSites(token, tenantSlug),
    ])
    setDomains(d)
    setSites(s)
  }, [tenantSlug])

  useEffect(() => {
    void load().finally(() => setLoading(false))
  }, [load])

  const handleAdd = async () => {
    const d = addDomain.trim().toLowerCase()
    if (!d || !addSiteId) return
    setSaving(true)
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const result = await createAdminDomain(token, tenantSlug, { domain: d, site_id: addSiteId })
    setSaving(false)
    if (result) {
      setSheetOpen(false)
      setAddDomain("")
      setAddSiteId("")
      void load()
    }
  }

  const handleRemove = async (domain: string) => {
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const ok = await deleteAdminDomain(token, tenantSlug, domain)
    if (ok) void load()
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Domains</CardTitle>
          <CardDescription>Manage custom domains for this tenant</CardDescription>
        </div>
        <Button onClick={() => setSheetOpen(true)}>Add domain</Button>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : domains.length === 0 ? (
          <p className="text-sm text-muted-foreground">No domains yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="pb-2 text-left font-medium">Domain</th>
                  <th className="pb-2 text-left font-medium">Site</th>
                  <th className="pb-2 text-left font-medium">Status</th>
                  <th className="pb-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {domains.map((d) => (
                  <tr key={d.domain} className="border-b">
                    <td className="py-3">{d.domain}</td>
                    <td className="py-3">{sites.find((s) => s.id === d.site_id)?.name ?? d.site_id}</td>
                    <td className="py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          d.status === "verified"
                            ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {d.status}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      <Button size="sm" variant="ghost" onClick={() => handleRemove(d.domain)}>Remove</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Add domain</SheetTitle>
          </SheetHeader>
          <div className="mt-4 space-y-4">
            <div>
              <label className="text-sm font-medium">Domain</label>
              <Input
                value={addDomain}
                onChange={(e) => setAddDomain(e.target.value)}
                placeholder="example.com"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Site</label>
              <select
                value={addSiteId}
                onChange={(e) => setAddSiteId(e.target.value)}
                className="mt-1 flex h-9 w-full rounded-md border border-input px-3 py-1 text-sm"
              >
                <option value="">Select site</option>
                {sites.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            <Button onClick={handleAdd} disabled={saving || !addDomain.trim() || !addSiteId}>
              {saving ? "Adding…" : "Add"}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </Card>
  )
}

function AdminSitesTab({ tenantSlug }: { tenantSlug: string }) {
  const [sites, setSites] = useState<Site[]>([])
  const [templates, setTemplates] = useState<{ slug: string; name: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editSite, setEditSite] = useState<Site | null>(null)
  const [name, setName] = useState("")
  const [slug, setSlug] = useState("")
  const [templateId, setTemplateId] = useState("")
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const [s, t] = await Promise.all([
      fetchAdminSites(token, tenantSlug),
      fetchAdminTemplates(token),
    ])
    setSites(s)
    setTemplates(t)
  }, [tenantSlug])

  useEffect(() => {
    void load().finally(() => setLoading(false))
  }, [load])

  const openCreate = () => {
    setEditSite(null)
    setName("")
    setSlug("")
    setTemplateId("")
    setSheetOpen(true)
  }

  const openEdit = (site: Site) => {
    setEditSite(site)
    setName(site.name)
    setSlug(site.slug)
    setTemplateId(site.template_id ?? "")
    setSheetOpen(true)
  }

  const handleSave = async () => {
    if (!name.trim()) return
    setSaving(true)
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    if (editSite) {
      const result = await updateAdminSite(token, tenantSlug, editSite.id, { name, slug: slug || undefined })
      if (result) { setSheetOpen(false); void load() }
    } else {
      const body: { name: string; slug?: string; template_id?: string } = { name: name.trim() }
      if (slug.trim()) body.slug = slug.trim().toLowerCase()
      if (templateId) body.template_id = templateId
      const result = await createAdminSite(token, tenantSlug, body)
      if (result) { setSheetOpen(false); void load() }
    }
    setSaving(false)
  }

  const handleDelete = async (siteId: string) => {
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const ok = await deleteAdminSite(token, tenantSlug, siteId)
    if (ok) void load()
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Sites</CardTitle>
          <CardDescription>Manage sites for this tenant</CardDescription>
        </div>
        <Button onClick={openCreate}>Add site</Button>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : sites.length === 0 ? (
          <p className="text-sm text-muted-foreground">No sites yet.</p>
        ) : (
          <div className="divide-y">
            {sites.map((s) => (
              <div key={s.id} className="flex items-center justify-between py-3">
                <div>
                  <span className="font-medium">{s.name}</span>
                  <span className="ml-2 text-sm text-muted-foreground">({s.slug})</span>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => openEdit(s)}>Edit</Button>
                  <Button size="sm" variant="ghost" onClick={() => handleDelete(s.id)}>Delete</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{editSite ? "Edit site" : "Add site"}</SheetTitle>
          </SheetHeader>
          <div className="mt-4 space-y-4">
            <div>
              <label className="text-sm font-medium">Name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
            </div>
            <div>
              <label className="text-sm font-medium">Slug</label>
              <Input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="my-site" className="mt-1" />
            </div>
            {!editSite && (
              <div>
                <label className="text-sm font-medium">Template</label>
                <select
                  value={templateId}
                  onChange={(e) => setTemplateId(e.target.value)}
                  className="mt-1 flex h-9 w-full rounded-md border border-input px-3 py-1 text-sm"
                >
                  <option value="">None</option>
                  {templates.map((t) => (
                    <option key={t.slug} value={t.slug}>{t.name}</option>
                  ))}
                </select>
              </div>
            )}
            <Button onClick={handleSave} disabled={saving || !name.trim()}>
              {saving ? "Saving…" : editSite ? "Save" : "Create"}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </Card>
  )
}

function AdminUsersTab({ tenantSlug }: { tenantSlug: string }) {
  const [users, setUsers] = useState<TenantUser[]>([])
  const [loading, setLoading] = useState(true)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [permUser, setPermUser] = useState<TenantUser | null>(null)
  const [editUser, setEditUser] = useState<TenantUser | null>(null)
  const [addEmail, setAddEmail] = useState("")
  const [addRole, setAddRole] = useState("member")
  const [saving, setSaving] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  const load = useCallback(async () => {
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const list = await fetchAdminTenantUsers(token, tenantSlug)
    setUsers(list)
  }, [tenantSlug])

  useEffect(() => {
    void load().finally(() => setLoading(false))
  }, [load])

  const handleAdd = async () => {
    const email = addEmail.trim()
    if (!email) return
    setAddError(null)
    setSaving(true)
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const result = await createAdminUser(token, tenantSlug, { email, role: addRole })
    setSaving(false)
    if (result.success) {
      setSheetOpen(false)
      setAddEmail("")
      setAddRole("member")
      void load()
    } else {
      setAddError(result.error)
    }
  }

  const handleRemove = async (userSub: string) => {
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const ok = await deleteAdminUser(token, tenantSlug, userSub)
    if (ok) void load()
  }

  const handleRoleChange = async (userSub: string, role: string) => {
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const result = await updateAdminUser(token, tenantSlug, userSub, { role })
    if (result) {
      setEditUser(null)
      void load()
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Users</CardTitle>
          <CardDescription>Manage users in this tenant</CardDescription>
        </div>
        <Button onClick={() => { setAddError(null); setSheetOpen(true) }}>Add user</Button>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : users.length === 0 ? (
          <p className="text-sm text-muted-foreground">No users yet.</p>
        ) : (
          <div className="divide-y">
            {users.map((u) => (
              <div key={u.sub} className="flex items-center justify-between py-3">
                <div>
                  <span className="font-medium">{u.name || u.email || u.sub}</span>
                  <span className="ml-2 text-sm text-muted-foreground">({u.role})</span>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => setEditUser(u)}>Edit role</Button>
                  <Button size="sm" variant="outline" onClick={() => setPermUser(u)}>Permissions</Button>
                  <Button size="sm" variant="ghost" onClick={() => handleRemove(u.sub)}>Remove</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Add user</SheetTitle>
          </SheetHeader>
          <div className="mt-4 space-y-4">
            <div>
              <label className="text-sm font-medium">Email</label>
              <Input
                type="email"
                value={addEmail}
                onChange={(e) => setAddEmail(e.target.value)}
                placeholder="user@example.com"
                className="mt-1"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Cognito user email. User must have an account.
              </p>
            </div>
            <div>
              <label className="text-sm font-medium">Role</label>
              <select
                value={addRole}
                onChange={(e) => setAddRole(e.target.value)}
                className="mt-1 flex h-9 w-full rounded-md border border-input px-3 py-1 text-sm"
              >
                <option value="admin">admin</option>
                <option value="manager">manager</option>
                <option value="editor">editor</option>
                <option value="member">member</option>
              </select>
            </div>
            {addError && (
              <p className="text-sm text-destructive">{addError}</p>
            )}
            <Button onClick={handleAdd} disabled={saving || !addEmail.trim()}>
              {saving ? "Adding…" : "Add"}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
      {editUser && (
        <EditRoleSheet
          user={editUser}
          onClose={() => setEditUser(null)}
          onSave={async (role) => {
            await handleRoleChange(editUser.sub, role)
          }}
        />
      )}
      {permUser && (
        <PermissionsSheet
          tenantSlug={tenantSlug}
          user={permUser}
          onClose={() => setPermUser(null)}
          onSaved={() => { void load(); setPermUser(null) }}
        />
      )}
    </Card>
  )
}

function EditRoleSheet({
  user,
  onClose,
  onSave,
}: {
  user: TenantUser
  onClose: () => void
  onSave: (role: string) => Promise<void>
}) {
  const [role, setRole] = useState(user.role)
  const [saving, setSaving] = useState(false)
  return (
    <Sheet open onOpenChange={(o) => !o && onClose()}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Edit role: {user.name || user.email || user.sub}</SheetTitle>
        </SheetHeader>
        <div className="mt-4 space-y-4">
          <div>
            <label className="text-sm font-medium">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="mt-1 flex h-9 w-full rounded-md border border-input px-3 py-1 text-sm"
            >
              <option value="admin">admin</option>
              <option value="manager">manager</option>
              <option value="editor">editor</option>
              <option value="member">member</option>
            </select>
          </div>
          <Button
            onClick={async () => {
              setSaving(true)
              await onSave(role)
              setSaving(false)
            }}
            disabled={saving}
          >
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}

function PermissionsSheet({
  tenantSlug,
  user,
  onClose,
  onSaved,
}: {
  tenantSlug: string
  user: TenantUser
  onClose: () => void
  onSaved: () => void
}) {
  const [perms, setPerms] = useState<ModulePermissions | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    async function load() {
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const p = await fetchAdminUserPermissions(token, tenantSlug, user.sub)
      setPerms(p ?? { sites: true, domains: true, analytics: true, settings: true, users: true })
      setLoading(false)
    }
    void load()
  }, [tenantSlug, user.sub])

  const handleSave = async () => {
    if (!perms) return
    setSaving(true)
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const result = await updateAdminUserPermissions(token, tenantSlug, user.sub, perms)
    setSaving(false)
    if (result) onSaved()
  }

  return (
    <Sheet open onOpenChange={(o) => !o && onClose()}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Permissions: {user.name || user.email || user.sub}</SheetTitle>
        </SheetHeader>
        <div className="mt-4 space-y-4">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : perms ? (
            <>
              {MODULE_KEYS.map((key) => (
                <label key={key} className="flex items-center justify-between rounded-lg border p-3">
                  <span className="capitalize">{key}</span>
                  <input
                    type="checkbox"
                    checked={perms[key]}
                    onChange={(e) => setPerms({ ...perms, [key]: e.target.checked })}
                    className="h-4 w-4"
                  />
                </label>
              ))}
              <Button onClick={handleSave} disabled={saving}>{saving ? "Saving…" : "Save"}</Button>
            </>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function AdminSettingsTab({
  tenant,
  onSaved,
}: {
  tenant: AdminTenantDetail
  onSaved: () => void
}) {
  const [name, setName] = useState(tenant.name)
  const [tier, setTier] = useState(tenant.tier)
  const [ownerSub, setOwnerSub] = useState(tenant.owner_sub ?? "")
  const [moduleOverrides, setModuleOverrides] = useState<Record<string, boolean>>(
    tenant.module_overrides ?? { custom_domains: false, advanced_analytics: false }
  )
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    setName(tenant.name)
    setTier(tenant.tier)
    setOwnerSub(tenant.owner_sub ?? "")
    setModuleOverrides(tenant.module_overrides ?? { custom_domains: false, advanced_analytics: false })
  }, [tenant.slug, tenant.name, tenant.tier, tenant.owner_sub, tenant.module_overrides])

  const handleSave = async () => {
    setSaveError(null)
    setSaving(true)
    const session = await fetchAuthSession()
    const token = session.tokens?.accessToken?.toString() ?? null
    const result = await putAdminTenantSettings(token, tenant.slug, {
      name,
      tier,
      owner_sub: ownerSub.trim() || undefined,
      module_overrides: moduleOverrides,
    })
    setSaving(false)
    if (result) {
      void onSaved()
    } else {
      setSaveError("Failed to save settings. Please try again.")
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Settings</CardTitle>
        <CardDescription>Update tenant configuration</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="text-sm font-medium">Name</label>
          <Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1" />
        </div>
        <div>
          <label className="text-sm font-medium">Tier</label>
          <select
            value={tier}
            onChange={(e) => setTier(e.target.value)}
            className="mt-1 flex h-9 w-full rounded-md border border-input px-3 py-1 text-sm"
          >
            <option value="FREE">Free</option>
            <option value="PRO">Pro</option>
            <option value="BUSINESS">Business</option>
          </select>
        </div>
        <div>
          <label className="text-sm font-medium">Owner</label>
          <p className="text-xs text-muted-foreground mt-1 space-y-0.5">
            {tenant.owner_email ? (
              <span className="block">{tenant.owner_email}</span>
            ) : null}
            {tenant.owner_sub ? (
              <span className="block text-muted-foreground">Cognito ID: {tenant.owner_sub}</span>
            ) : null}
            {!tenant.owner_email && !tenant.owner_sub ? (
              <span className="text-muted-foreground">—</span>
            ) : null}
          </p>
          <Input
            value={ownerSub}
            onChange={(e) => setOwnerSub(e.target.value)}
            placeholder="Cognito sub (for transfer)"
            className="mt-2"
          />
        </div>
        <div>
          <label className="text-sm font-medium">Module overrides</label>
          <div className="mt-2 space-y-2">
            {FEATURE_KEYS.map((key) => (
              <label key={key} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={moduleOverrides[key] ?? false}
                  onChange={(e) => setModuleOverrides((m) => ({ ...m, [key]: e.target.checked }))}
                  className="h-4 w-4"
                />
                <span className="text-sm capitalize">{key.replace("_", " ")}</span>
              </label>
            ))}
          </div>
        </div>
        {saveError && (
          <p className="text-sm text-destructive">{saveError}</p>
        )}
        <Button onClick={handleSave} disabled={saving}>{saving ? "Saving…" : "Save"}</Button>
      </CardContent>
    </Card>
  )
}

export { AdministerTenantPage }
