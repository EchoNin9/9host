"use client"

import { useEffect, useState } from "react"
import { Shield, Settings2 } from "lucide-react"
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
import { useTenant } from "@/hooks/use-tenant"
import { useTenantRole } from "@/hooks/use-tenant-role"
import { useTenantUsers, useUserPermissions } from "@/hooks/use-tenant-users"
import { MODULE_KEYS, type TenantUser, type ModulePermissions } from "@/lib/api"

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

function TenantUsers() {
  const { tenantSlug } = useTenant()
  const { canEdit } = useTenantRole()
  const { users, loading, error } = useTenantUsers(tenantSlug)
  const [permissionsUser, setPermissionsUser] = useState<TenantUser | null>(null)

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
      <div>
        <h1 className="text-2xl font-semibold">Users</h1>
        <p className="text-muted-foreground">
          Tenant members and their roles. Configure module access per user.
        </p>
      </div>

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
            <p className="text-sm text-muted-foreground">Loading users…</p>
          </CardContent>
        </Card>
      ) : users.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Tenant users</CardTitle>
            <CardDescription>
              No users in this tenant yet. Users are added when they join.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="space-y-2">
          {users.map((u) => (
            <Card key={u.sub}>
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
        </div>
      )}

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
