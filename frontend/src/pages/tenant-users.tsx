"use client"

import { useEffect, useState } from "react"
import { NativeSelect } from "@/components/ui/native-select"
import { Crown, Lock, Pencil, Plus, Settings2, Shield, Trash2, Users } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState, LoadingState, Notice } from "@/components/page"
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
import { useTenantScope } from "@/context/tenant-scope-context"
import { useTenantMetadata } from "@/hooks/use-tenant-metadata"
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
import { TenantPage, TenantPageHeader } from "@/components/tenant-page"

function Avatar({ label }: { label: string }) {
  const parts = label.split(/[\s@._-]+/).filter(Boolean)
  const text = ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?"
  return (
    <span
      aria-hidden
      className="flex size-8 shrink-0 items-center justify-center rounded-full border bg-muted font-mono text-[0.6875rem] font-semibold"
    >
      {text}
    </span>
  )
}

function PermissionsForm({
  user,
  ownerSub,
  onClose,
  onSaved,
}: {
  user: TenantUser
  ownerSub: string | null
  onClose: () => void
  onSaved: () => void
}) {
  const isOwner = ownerSub != null && user.sub === ownerSub
  const { permissions, loading, update } = useUserPermissions(user.sub)
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

  if (isOwner) {
    return (
      <div className="flex flex-col gap-6">
        <p className="text-sm text-muted-foreground">
          The account owner has full access to all modules. Permissions cannot be edited.
        </p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-muted-foreground">
        Configure which modules {user.name || user.email || user.sub} can access.
      </p>
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : local ? (
        <div className="divide-y overflow-hidden rounded-md border">
          {MODULE_KEYS.map((key) => (
            <label
              key={key}
              className="flex cursor-pointer items-center justify-between gap-3 px-3 py-2.5 hover:bg-accent/50"
            >
              <span className="text-sm capitalize">{key}</span>
              <Switch checked={local[key]} onCheckedChange={() => handleToggle(key)} aria-label={`Allow ${key}`} />
            </label>
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
  roles,
  onClose,
  onSaved,
}: {
  roles: { name: string }[]
  onClose: () => void
  onSaved: () => void
}) {
  const { api } = useTenantScope()
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
      const created = await createTenantTUser(api, token, {
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
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <div>
        <label htmlFor="tuser-username" className="text-sm font-medium">
          Username
        </label>
        <Input
          id="tuser-username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="jane"
          className="mt-1.5"
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
          className="mt-1.5"
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
          className="mt-1.5"
        />
      </div>
      <div>
        <label htmlFor="tuser-role" className="text-sm font-medium">
          Role
        </label>
        <NativeSelect
          className="mt-1.5"
          id="tuser-role"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          {roleOptions.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </NativeSelect>
      </div>
      {err && <Notice tone="danger">{err}</Notice>}
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
  roles,
  onClose,
  onSaved,
}: {
  user: TenantTUser
  roles: { name: string }[]
  onClose: () => void
  onSaved: () => void
}) {
  const { api } = useTenantScope()
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
      const updated = await updateTenantTUser(api, token, user.username, body)
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
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
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
          className="mt-1.5"
        />
      </div>
      <div>
        <label htmlFor="edit-role" className="text-sm font-medium">
          Role
        </label>
        <NativeSelect
          className="mt-1.5"
          id="edit-role"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          {roleOptions.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </NativeSelect>
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
          className="mt-1.5"
          autoComplete="new-password"
          minLength={8}
        />
      </div>
      {err && <Notice tone="danger">{err}</Notice>}
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
  onClose,
  onSaved,
}: {
  onClose: () => void
  onSaved: () => void
}) {
  const { api } = useTenantScope()
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
      const created = await createTenantRole(api, token, {
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
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <div>
        <label htmlFor="role-name" className="text-sm font-medium">
          Role name
        </label>
        <Input
          id="role-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="writer"
          className="mt-1.5"
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Alphanumeric, underscores, hyphens. Reserved: manager, member, admin, editor
        </p>
      </div>
      <div>
        <label className="text-sm font-medium">Permissions</label>
        <div className="mt-2 divide-y overflow-hidden rounded-md border">
          {MODULE_KEYS.map((key) => (
            <label
              key={key}
              className="flex cursor-pointer items-center justify-between gap-3 px-3 py-2.5 hover:bg-accent/50"
            >
              <span className="text-sm capitalize">{key}</span>
              <Switch checked={permissions[key] ?? false} onCheckedChange={() => handleToggle(key)} aria-label={`Allow ${key}`} />
            </label>
          ))}
        </div>
      </div>
      {err && <Notice tone="danger">{err}</Notice>}
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
  onClose,
  onSaved,
}: {
  role: TenantRole
  onClose: () => void
  onSaved: () => void
}) {
  const { api } = useTenantScope()
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
      const updated = await updateTenantRole(api, token, role.name, {
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
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <div>
        <label className="text-sm font-medium">Role name</label>
        <p className="mt-1 text-sm text-muted-foreground">{role.name}</p>
      </div>
      <div>
        <label className="text-sm font-medium">Permissions</label>
        <div className="mt-2 divide-y overflow-hidden rounded-md border">
          {MODULE_KEYS.map((key) => (
            <label
              key={key}
              className="flex cursor-pointer items-center justify-between gap-3 px-3 py-2.5 hover:bg-accent/50"
            >
              <span className="text-sm capitalize">{key}</span>
              <Switch checked={permissions[key] ?? false} onCheckedChange={() => handleToggle(key)} aria-label={`Allow ${key}`} />
            </label>
          ))}
        </div>
      </div>
      {err && <Notice tone="danger">{err}</Notice>}
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
  const { api } = useTenantScope()
  const { canEdit } = useTenantRole()
  const { tenant } = useTenantMetadata()
  const { users, loading, error } = useTenantUsers()
  const { tusers, loading: tloading, error: terror, refetch: refetchTUsers } = useTenantTUsers()
  const { roles, loading: rolesLoading, refetch: refetchRoles } = useTenantRoles()
  const [permissionsUser, setPermissionsUser] = useState<TenantUser | null>(null)
  const [addUserOpen, setAddUserOpen] = useState(false)
  const [editTUser, setEditTUser] = useState<TenantTUser | null>(null)
  const [deleteTUser, setDeleteTUser] = useState<TenantTUser | null>(null)
  const [addRoleOpen, setAddRoleOpen] = useState(false)
  const [editRole, setEditRole] = useState<TenantRole | null>(null)
  const [deleteRole, setDeleteRole] = useState<TenantRole | null>(null)

  if (!canEdit) {
    return (
      <TenantPage>
        <TenantPageHeader title="Users & roles" />
        <EmptyState
          icon={Lock}
          title="Admin or manager access required"
          description="Ask a tenant admin if you need to manage who can sign in here."
        />
      </TenantPage>
    )
  }

  const memberCount = users.length + tusers.length

  return (
    <TenantPage>
      <TenantPageHeader
        title="Users & roles"
        description="Members sign in with an Echo9 account. Site users sign in with a username you create here."
        actions={
          <Button onClick={() => setAddUserOpen(true)}>
            <Plus className="size-4" />
            Add site user
          </Button>
        }
      />

      {(error || terror) && <Notice tone="danger">{error || terror}</Notice>}

      <Card className="gap-0 py-0">
        <CardHeader className="flex flex-row items-center justify-between border-b py-4">
          <div>
            <CardTitle>
              Members <span className="tabular font-normal text-muted-foreground">{!(loading || tloading) && memberCount}</span>
            </CardTitle>
            <CardDescription>Everyone who can sign in to this tenant.</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="px-0">
          {loading || tloading ? (
            <LoadingState className="p-5" rows={2} label="Loading users…" />
          ) : memberCount === 0 ? (
            <EmptyState
              className="m-5"
              icon={Users}
              title="No users yet"
              description="Add a site user to give someone a username and password for this tenant."
            />
          ) : (
            <ul className="divide-y">
              {users.map((u) => {
                const isOwner = tenant?.owner_sub != null && u.sub === tenant.owner_sub
                const display = u.name || u.email || u.sub
                return (
                  <li key={`cognito-${u.sub}`} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
                    <Avatar label={display} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{display}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {u.email && u.email !== (u.name || u.sub) ? u.email : u.sub}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {isOwner && (
                        <Badge tone="warning">
                          <Crown aria-hidden />
                          Owner
                        </Badge>
                      )}
                      <Badge tone={u.role === "admin" ? "brand" : u.role === "manager" ? "info" : "neutral"}>
                        <Shield aria-hidden />
                        {u.role}
                      </Badge>
                      <Badge mono>account</Badge>
                    </div>
                    <div className="flex w-full justify-end gap-1 sm:w-auto">
                      {!isOwner && (
                        <Button variant="ghost" size="sm" onClick={() => setPermissionsUser(u)}>
                          <Settings2 className="size-4" />
                          Permissions
                        </Button>
                      )}
                    </div>
                  </li>
                )
              })}
              {tusers.map((u) => (
                <li key={`tuser-${u.username}`} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
                  <Avatar label={u.display_name || u.username} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{u.display_name || u.username}</p>
                    <p className="truncate font-mono text-xs text-muted-foreground">@{u.username}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={u.role === "manager" ? "info" : "neutral"}>{u.role}</Badge>
                    <Badge mono>site login</Badge>
                  </div>
                  <div className="flex w-full justify-end gap-1 sm:w-auto">
                    <Button variant="ghost" size="sm" onClick={() => setEditTUser(u)}>
                      <Pencil className="size-4" />
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => setDeleteTUser(u)}
                      aria-label={`Delete ${u.display_name || u.username}`}
                    >
                      <Trash2 className="size-4 text-destructive" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card className="gap-0 py-0">
        <CardHeader className="flex flex-row items-center justify-between gap-4 border-b py-4">
          <div>
            <CardTitle>Custom roles</CardTitle>
            <CardDescription>
              Bundles of module permissions you can assign to site users.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={() => setAddRoleOpen(true)}>
            <Plus className="size-4" />
            New role
          </Button>
        </CardHeader>
        <CardContent className="px-0">
          {rolesLoading ? (
            <LoadingState className="p-5" rows={1} label="Loading roles…" />
          ) : roles.length === 0 ? (
            <p className="px-5 py-6 text-sm text-muted-foreground">
              No custom roles yet. Built-in roles are admin, manager and member.
            </p>
          ) : (
            <ul className="divide-y">
              {roles.map((r) => {
                const allowed = MODULE_KEYS.filter((k) => r.permissions[k])
                return (
                  <li key={r.name} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-mono text-sm font-medium">{r.name}</p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {allowed.length ? (
                          allowed.map((k) => (
                            <Badge key={k} className="capitalize">
                              {k}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-xs text-muted-foreground">No permissions</span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => setEditRole(r)}>
                        <Pencil className="size-4" />
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => setDeleteRole(r)}
                        aria-label={`Delete role ${r.name}`}
                      >
                        <Trash2 className="size-4 text-destructive" />
                      </Button>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      <Sheet
        open={addUserOpen}
        onOpenChange={(open) => !open && setAddUserOpen(false)}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Add site user</SheetTitle>
            <SheetDescription>
              They sign in at Site sign-in with this username and password — no Echo9 account needed.
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4">
            {tenantSlug && (
              <AddTUserForm
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

      <ConfirmDialog
        open={!!deleteTUser}
        onOpenChange={(open) => !open && setDeleteTUser(null)}
        title={`Delete ${deleteTUser?.display_name || deleteTUser?.username || "user"}?`}
        description="They will no longer be able to sign in to this tenant."
        confirmLabel="Delete user"
        onConfirm={async () => {
          if (!deleteTUser || !tenantSlug) return false
          const token = await getToken()
          const ok = await deleteTenantTUser(api, token, deleteTUser.username)
          if (ok) refetchTUsers()
          return ok
        }}
      />

      <Sheet
        open={addRoleOpen}
        onOpenChange={(open) => !open && setAddRoleOpen(false)}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>New role</SheetTitle>
            <SheetDescription>
              Define a custom role with specific module permissions.
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4">
            {tenantSlug && (
              <AddRoleForm
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

      <ConfirmDialog
        open={!!deleteRole}
        onOpenChange={(open) => !open && setDeleteRole(null)}
        title={`Delete role ${deleteRole?.name ?? ""}?`}
        description="This fails if any users are still assigned to the role."
        confirmLabel="Delete role"
        onConfirm={async () => {
          if (!deleteRole || !tenantSlug) return false
          const token = await getToken()
          const ok = await deleteTenantRole(api, token, deleteRole.name)
          if (ok) refetchRoles()
          return ok
        }}
      />

      <Sheet
        open={!!permissionsUser}
        onOpenChange={(open) => !open && setPermissionsUser(null)}
      >
        <SheetContent>
          <SheetHeader>
            <SheetTitle>Module permissions</SheetTitle>
            <SheetDescription>
              {permissionsUser?.name || permissionsUser?.email || permissionsUser?.sub}
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4">
            {permissionsUser && tenantSlug && (
              <PermissionsForm
                user={permissionsUser}
                ownerSub={tenant?.owner_sub ?? null}
                onClose={() => setPermissionsUser(null)}
                onSaved={() => {}}
              />
            )}
          </div>
        </SheetContent>
      </Sheet>
    </TenantPage>
  )
}

export { TenantUsers }
