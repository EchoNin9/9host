"use client"

import { useEffect, useState } from "react"
import { Pencil, Plus, Shield, Settings2, Trash2, User } from "lucide-react"
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
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  createTenantRole,
  createTenantTUser,
  deleteTenantRole,
  deleteTenantTUser,
  getToken,
  updateTenantRole,
  updateTenantTUser,
} from "@/lib/api"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantRole } from "@/hooks/use-tenant-role"
import {
  useTenantUsers,
  useTenantTUsers,
  useTenantRoles,
  useUserPermissions,
} from "@/hooks/use-tenant-users"
import {
  MODULE_KEYS,
  type TenantRole,
  type TenantTUser,
  type TenantUser,
  type ModulePermissions,
} from "@/lib/api"

function PermissionsForm({
  user,
  tenantSlug,
  onClose,
  onSaved,
}: {
  user: TenantUser
  tenantSlug: string
  onClose: () => void
  onSaved: () => void
}) {
  const { permissions, loading, update } = useUserPermissions(
    tenantSlug,
    user.sub
  )
  const [local, setLocal] = useState<ModulePermissions | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (permissions) setLocal(permissions)
  }, [permissions])

  const handleToggle = (key: (typeof MODULE_KEYS)[number]) => {
    if (!local) return
    setLocal({ ...local, [key]: !local[key] })
  }

  const handleSave = async () => {
    if (!local) return
    setSaving(true)
    const ok = await update(local)
    setSaving(false)
    if (ok) {
      onSaved()
      onClose()
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-muted-foreground">
        Configure which modules {user.name || user.email || user.sub} can access.
      </p>
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : local ? (
        <div className="space-y-3">
          {MODULE_KEYS.map((key) => (
            <div
              key={key}
              className="flex items-center justify-between rounded-lg border p-3"
            >
              <span className="capitalize">{key}</span>
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={local[key]}
                  onChange={() => handleToggle(key)}
                  className="h-4 w-4 rounded border-input"
                />
                <span className="text-sm">Allow</span>
              </label>
            </div>
          ))}
        </div>
      ) : null}
      <div className="flex gap-2">
        <Button variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={saving || !local}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  )
}

function AddTUserForm({
  tenantSlug,
  roles,
  onClose,
  onSaved,
}: {
  tenantSlug: string
  roles: { name: string }[]
  onClose: () => void
  onSaved: () => void
}) {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [role, setRole] = useState("member")
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const roleOptions = [
    { value: "manager", label: "Manager" },
    { value: "member", label: "Member" },
    ...roles.map((r) => ({ value: r.name, label: r.name })),
  ]

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr(null)
    if (!username.trim()) {
      setErr("Username is required")
      return
    }
    if (!password || password.length < 8) {
      setErr("Password must be at least 8 characters")
      return
    }
    setSaving(true)
    try {
      const token = await getToken()
      const created = await createTenantTUser(tenantSlug, token, {
        username: username.trim().toLowerCase(),
        password,
        display_name: displayName.trim() || undefined,
        role,
      })
      if (created) {
        onSaved()
        onClose()
      } else {
        setErr("Failed to create user")
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to create user")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label htmlFor="tuser-username" className="text-sm font-medium">
          Username
        </label>
        <Input
          id="tuser-username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="jane"
          className="mt-1"
          autoComplete="username"
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Alphanumeric, dots, underscores, hyphens
        </p>
      </div>
      <div>
        <label htmlFor="tuser-password" className="text-sm font-medium">
          Password
        </label>
        <Input
          id="tuser-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          className="mt-1"
          autoComplete="new-password"
          minLength={8}
        />
      </div>
      <div>
        <label htmlFor="tuser-display" className="text-sm font-medium">
          Display name (optional)
        </label>
        <Input
          id="tuser-display"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Jane Doe"
          className="mt-1"
        />
      </div>
      <div>
        <label htmlFor="tuser-role" className="text-sm font-medium">
          Role
        </label>
        <select
          id="tuser-role"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
        >
          {roleOptions.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      {err && <p className="text-sm text-destructive">{err}</p>}
      <SheetFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? "Creating…" : "Add user"}
        </Button>
      </SheetFooter>
    </form>
  )
}

function EditTUserForm({
  user,
  tenantSlug,
  roles,
  onClose,
  onSaved,
}: {
  user: TenantTUser
  tenantSlug: string
  roles: { name: string }[]
  onClose: () => void
  onSaved: () => void
}) {
  const [displayName, setDisplayName] = useState(user.display_name || "")
  const [role, setRole] = useState(user.role)
  const [password, setPassword] = useState("")
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const roleOptions = [
    { value: "manager", label: "Manager" },
    { value: "member", label: "Member" },
    ...roles.map((r) => ({ value: r.name, label: r.name })),
  ]

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr(null)
    if (password && password.length < 8) {
      setErr("Password must be at least 8 characters")
      return
    }
    setSaving(true)
    try {
      const token = await getToken()
      const body: { role?: string; display_name?: string; password?: string } = {
        role,
        display_name: displayName.trim() || undefined,
      }
      if (password) body.password = password
      const updated = await updateTenantTUser(tenantSlug, token, user.username, body)
      if (updated) {
        onSaved()
        onClose()
      } else {
        setErr("Failed to update user")
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to update user")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label className="text-sm font-medium">Username</label>
        <p className="mt-1 text-sm text-muted-foreground">{user.username}</p>
      </div>
      <div>
        <label htmlFor="edit-display" className="text-sm font-medium">
          Display name
        </label>
        <Input
          id="edit-display"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Jane Doe"
          className="mt-1"
        />
      </div>
      <div>
        <label htmlFor="edit-role" className="text-sm font-medium">
          Role
        </label>
        <select
          id="edit-role"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
        >
          {roleOptions.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="edit-password" className="text-sm font-medium">
          New password (optional)
        </label>
        <Input
          id="edit-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Leave blank to keep current"
          className="mt-1"
          autoComplete="new-password"
          minLength={8}
        />
      </div>
      {err && <p className="text-sm text-destructive">{err}</p>}
      <SheetFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </SheetFooter>
    </form>
  )
}

function AddRoleForm({
  tenantSlug,
  onClose,
  onSaved,
}: {
  tenantSlug: string
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState("")
  const [permissions, setPermissions] = useState<Record<string, boolean>>({
    sites: false,
    domains: false,
    analytics: false,
    settings: false,
    users: false,
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const handleToggle = (key: string) => {
    setPermissions((p) => ({ ...p, [key]: !p[key] }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr(null)
    const n = name.trim().toLowerCase()
    if (!n) {
      setErr("Name is required")
      return
    }
    if (["manager", "member", "admin", "editor"].includes(n)) {
      setErr("That role name is reserved")
      return
    }
    setSaving(true)
    try {
      const token = await getToken()
      const created = await createTenantRole(tenantSlug, token, {
        name: n,
        permissions,
      })
      if (created) {
        onSaved()
        onClose()
      } else {
        setErr("Failed to create role")
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to create role")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label htmlFor="role-name" className="text-sm font-medium">
          Role name
        </label>
        <Input
          id="role-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="editor"
          className="mt-1"
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Alphanumeric, underscores, hyphens. Reserved: manager, member, admin, editor
        </p>
      </div>
      <div>
        <label className="text-sm font-medium">Permissions</label>
        <div className="mt-2 space-y-2">
          {MODULE_KEYS.map((key) => (
            <div
              key={key}
              className="flex items-center justify-between rounded-lg border p-3"
            >
              <span className="capitalize">{key}</span>
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={permissions[key] ?? false}
                  onChange={() => handleToggle(key)}
                  className="h-4 w-4 rounded border-input"
                />
                <span className="text-sm">Allow</span>
              </label>
            </div>
          ))}
        </div>
      </div>
      {err && <p className="text-sm text-destructive">{err}</p>}
      <SheetFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? "Creating…" : "Create role"}
        </Button>
      </SheetFooter>
    </form>
  )
}

function EditRoleForm({
  role,
  tenantSlug,
  onClose,
  onSaved,
}: {
  role: TenantRole
  tenantSlug: string
  onClose: () => void
  onSaved: () => void
}) {
  const [permissions, setPermissions] = useState(role.permissions)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const handleToggle = (key: string) => {
    setPermissions((p) => ({ ...p, [key]: !(p[key] ?? false) }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr(null)
    setSaving(true)
    try {
      const token = await getToken()
      const updated = await updateTenantRole(tenantSlug, token, role.name, {
        permissions,
      })
      if (updated) {
        onSaved()
        onClose()
      } else {
        setErr("Failed to update role")
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to update role")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label className="text-sm font-medium">Role name</label>
        <p className="mt-1 text-sm text-muted-foreground">{role.name}</p>
      </div>
      <div>
        <label className="text-sm font-medium">Permissions</label>
        <div className="mt-2 space-y-2">
          {MODULE_KEYS.map((key) => (
            <div
              key={key}
              className="flex items-center justify-between rounded-lg border p-3"
            >
              <span className="capitalize">{key}</span>
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={permissions[key] ?? false}
                  onChange={() => handleToggle(key)}
                  className="h-4 w-4 rounded border-input"
                />
                <span className="text-sm">Allow</span>
              </label>
            </div>
          ))}
        </div>
      </div>
      {err && <p className="text-sm text-destructive">{err}</p>}
      <SheetFooter>
        <Button type="button" variant="outline" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </SheetFooter>
    </form>
  )
}

function TenantUsers() {
  const { tenantSlug } = useTenant()
  const { canEdit } = useTenantRole()
  const { users, loading, error } = useTenantUsers(tenantSlug)
  const { tusers, loading: tloading, error: terror, refetch: refetchTUsers } = useTenantTUsers(tenantSlug)
  const { roles, loading: rolesLoading, refetch: refetchRoles } = useTenantRoles(tenantSlug)
  const [permissionsUser, setPermissionsUser] = useState<TenantUser | null>(null)
  const [addUserOpen, setAddUserOpen] = useState(false)
  const [editTUser, setEditTUser] = useState<TenantTUser | null>(null)
  const [deleteTUser, setDeleteTUser] = useState<TenantTUser | null>(null)
  const [addRoleOpen, setAddRoleOpen] = useState(false)
  const [editRole, setEditRole] = useState<TenantRole | null>(null)
  const [deleteRole, setDeleteRole] = useState<TenantRole | null>(null)

  if (!canEdit) {
    return (
      <div className="flex flex-1 flex-col gap-6 p-6">
        <div>
          <h1 className="text-2xl font-semibold">Users</h1>
          <p className="text-muted-foreground">
            Admin or manager access required to view tenant users.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Users</h1>
          <p className="text-muted-foreground">
            Tenant members and their roles. Cognito users can configure module access.
          </p>
        </div>
        <Button onClick={() => setAddUserOpen(true)}>
          <Plus className="mr-2 size-4" />
          Add user
        </Button>
      </div>

      {(error || terror) && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error || terror}</p>
          </CardContent>
        </Card>
      )}

      {(loading || tloading) ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Loading users…</p>
          </CardContent>
        </Card>
      ) : users.length === 0 && tusers.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Tenant users</CardTitle>
            <CardDescription>
              No users in this tenant yet. Add a non-Cognito user or invite Cognito users.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="space-y-2">
          {users.map((u) => (
            <Card key={`cognito-${u.sub}`}>
              <CardHeader className="flex flex-row items-center justify-between py-4">
                <div>
                  <CardTitle className="text-base">
                    {u.name || u.email || u.sub}
                  </CardTitle>
                  <CardDescription>
                    {u.email && u.email !== (u.name || u.sub) ? u.email : u.sub}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                      u.role === "admin"
                        ? "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400"
                        : u.role === "manager"
                          ? "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400"
                          : "bg-muted text-muted-foreground"
                    }`}
                  >
                    <Shield className="size-3" />
                    {u.role}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPermissionsUser(u)}
                  >
                    <Settings2 className="mr-1 size-4" />
                    Permissions
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ))}
          {tusers.map((u) => (
            <Card key={`tuser-${u.username}`}>
              <CardHeader className="flex flex-row items-center justify-between py-4">
                <div>
                  <CardTitle className="text-base flex items-center gap-2">
                    <User className="size-4 text-muted-foreground" />
                    {u.display_name || u.username}
                  </CardTitle>
                  <CardDescription>
                    {u.display_name ? u.username : `@${u.username}`}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                      u.role === "manager"
                        ? "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {u.role}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setEditTUser(u)}
                  >
                    <Pencil className="mr-1 size-4" />
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setDeleteTUser(u)}
                  >
                    <Trash2 className="mr-1 size-4" />
                    Delete
                  </Button>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between py-4">
          <div>
            <CardTitle className="text-base">Custom roles</CardTitle>
            <CardDescription>
              Define roles with specific permissions. Assign to users when adding or editing.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => setAddRoleOpen(true)}>
            <Plus className="mr-2 size-4" />
            Create role
          </Button>
        </CardHeader>
        <CardContent>
          {rolesLoading ? (
            <p className="text-sm text-muted-foreground">Loading roles…</p>
          ) : roles.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No custom roles. Create one to assign granular permissions.
            </p>
          ) : (
            <div className="space-y-2">
              {roles.map((r) => (
                <div
                  key={r.name}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div>
                    <span className="font-medium">{r.name}</span>
                    <p className="text-xs text-muted-foreground">
                      {MODULE_KEYS.filter((k) => r.permissions[k]).join(", ") || "No permissions"}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setEditRole(r)}
                    >
                      <Pencil className="mr-1 size-4" />
                      Edit
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setDeleteRole(r)}
                    >
                      <Trash2 className="mr-1 size-4" />
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Sheet
        open={addUserOpen}
        onOpenChange={(open) => !open && setAddUserOpen(false)}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Add user</SheetTitle>
            <SheetDescription>
              Create a non-Cognito user who can sign in with username and password.
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4">
            {tenantSlug && (
              <AddTUserForm
                tenantSlug={tenantSlug}
                roles={roles}
                onClose={() => setAddUserOpen(false)}
                onSaved={() => {
                  refetchTUsers()
                  refetchRoles()
                }}
              />
            )}
          </div>
        </SheetContent>
      </Sheet>

      <Sheet
        open={!!editTUser}
        onOpenChange={(open) => !open && setEditTUser(null)}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Edit user</SheetTitle>
            <SheetDescription>
              {editTUser?.display_name || editTUser?.username}
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4">
            {editTUser && tenantSlug && (
              <EditTUserForm
                user={editTUser}
                tenantSlug={tenantSlug}
                roles={roles}
                onClose={() => setEditTUser(null)}
                onSaved={() => {
                  refetchTUsers()
                  setEditTUser(null)
                }}
              />
            )}
          </div>
        </SheetContent>
      </Sheet>

      <Sheet
        open={!!deleteTUser}
        onOpenChange={(open) => !open && setDeleteTUser(null)}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Delete user</SheetTitle>
            <SheetDescription>
              Remove {deleteTUser?.display_name || deleteTUser?.username} from this tenant? They will no longer be able to sign in.
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4 flex gap-2">
            <Button variant="outline" onClick={() => setDeleteTUser(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={async () => {
                if (!deleteTUser || !tenantSlug) return
                const token = await getToken()
                const ok = await deleteTenantTUser(tenantSlug, token, deleteTUser.username)
                if (ok) {
                  refetchTUsers()
                  setDeleteTUser(null)
                }
              }}
            >
              Delete
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      <Sheet
        open={addRoleOpen}
        onOpenChange={(open) => !open && setAddRoleOpen(false)}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Create role</SheetTitle>
            <SheetDescription>
              Define a custom role with specific module permissions.
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4">
            {tenantSlug && (
              <AddRoleForm
                tenantSlug={tenantSlug}
                onClose={() => setAddRoleOpen(false)}
                onSaved={() => {
                  refetchRoles()
                  setAddRoleOpen(false)
                }}
              />
            )}
          </div>
        </SheetContent>
      </Sheet>

      <Sheet
        open={!!editRole}
        onOpenChange={(open) => !open && setEditRole(null)}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Edit role</SheetTitle>
            <SheetDescription>{editRole?.name}</SheetDescription>
          </SheetHeader>
          <div className="mt-4">
            {editRole && tenantSlug && (
              <EditRoleForm
                role={editRole}
                tenantSlug={tenantSlug}
                onClose={() => setEditRole(null)}
                onSaved={() => {
                  refetchRoles()
                  setEditRole(null)
                }}
              />
            )}
          </div>
        </SheetContent>
      </Sheet>

      <Sheet
        open={!!deleteRole}
        onOpenChange={(open) => !open && setDeleteRole(null)}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Delete role</SheetTitle>
            <SheetDescription>
              Remove role {deleteRole?.name}? This will fail if any users are assigned to it.
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4 flex gap-2">
            <Button variant="outline" onClick={() => setDeleteRole(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={async () => {
                if (!deleteRole || !tenantSlug) return
                const token = await getToken()
                const ok = await deleteTenantRole(tenantSlug, token, deleteRole.name)
                if (ok) {
                  refetchRoles()
                  setDeleteRole(null)
                }
              }}
            >
              Delete
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      <Sheet
        open={!!permissionsUser}
        onOpenChange={(open) => !open && setPermissionsUser(null)}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>
              Module permissions
              {permissionsUser && (
                <span className="font-normal text-muted-foreground">
                  {" "}
                  — {permissionsUser.name || permissionsUser.email || permissionsUser.sub}
                </span>
              )}
            </SheetTitle>
          </SheetHeader>
          <div className="mt-4">
            {permissionsUser && tenantSlug && (
              <PermissionsForm
                user={permissionsUser}
                tenantSlug={tenantSlug}
                onClose={() => setPermissionsUser(null)}
                onSaved={() => {}}
              />
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}

export { TenantUsers }
