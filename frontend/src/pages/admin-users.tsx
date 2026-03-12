"use client"

import { useEffect, useState, useMemo } from "react"
import { Link } from "react-router-dom"
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
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { fetchAdminUsers, type AdminUserItem, type AdminUsersResponse } from "@/lib/api"
import { ChevronDown, ChevronRight, UserRound } from "lucide-react"

type SortDir = "a-z" | "z-a"

function getUserDisplayEmail(u: AdminUserItem): string {
  if (u.type === "cognito") return u.email ?? u.sub ?? ""
  return u.username ?? ""
}

function getUserDisplayName(u: AdminUserItem): string {
  if (u.type === "cognito") return u.name ?? u.email ?? u.sub ?? ""
  return u.display_name ?? u.username ?? ""
}

function AdminUsersPage() {
  const [data, setData] = useState<AdminUsersResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [sortDir, setSortDir] = useState<SortDir>("a-z")

  useEffect(() => {
    async function load() {
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const d = await fetchAdminUsers(token)
      setData(d ?? { users_by_tenant: {}, orphaned: [] })
      setLoading(false)
    }
    void load()
  }, [])

  const sortedTenantSlugs = useMemo(() => {
    if (!data) return []
    return Object.keys(data.users_by_tenant).sort((a, b) =>
      sortDir === "a-z" ? a.localeCompare(b) : b.localeCompare(a)
    )
  }, [data, sortDir])

  const sortUsers = (users: AdminUserItem[]) => {
    return [...users].sort((a, b) => {
      const emailA = getUserDisplayEmail(a).toLowerCase()
      const emailB = getUserDisplayEmail(b).toLowerCase()
      return sortDir === "a-z"
        ? emailA.localeCompare(emailB)
        : emailB.localeCompare(emailA)
    })
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        Loading…
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Users</h1>
          <p className="text-muted-foreground">
            All users across tenants. Grouped by tenant.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setSortDir((d) => (d === "a-z" ? "z-a" : "a-z"))}
        >
          Sort: {sortDir === "a-z" ? "A–Z" : "Z–A"}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Users by tenant</CardTitle>
          <CardDescription>
            Expand each tenant to see users. Orphaned users have no tenant.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {sortedTenantSlugs.map((slug) => (
            <TenantUserGroup
              key={slug}
              tenantSlug={slug}
              users={sortUsers(data!.users_by_tenant[slug] ?? [])}
            />
          ))}

          {data!.orphaned.length > 0 && (
            <Collapsible defaultOpen>
              <CollapsibleTrigger asChild>
                <button className="flex w-full items-center gap-2 rounded-lg border p-3 text-left font-medium hover:bg-muted/50">
                  <ChevronRight className="size-4 collapse-icon" />
                  <UserRound className="size-4" />
                  Orphaned users ({data!.orphaned.length})
                </button>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="ml-6 mt-2 space-y-2 border-l pl-4">
                  {sortUsers(data!.orphaned).map((u) => (
                    <UserRow key={u.sub ?? u.username} user={u} tenantSlug={null} />
                  ))}
                </div>
              </CollapsibleContent>
            </Collapsible>
          )}

          {sortedTenantSlugs.length === 0 && data!.orphaned.length === 0 && (
            <p className="text-sm text-muted-foreground">No users yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function TenantUserGroup({
  tenantSlug,
  users,
}: {
  tenantSlug: string
  users: AdminUserItem[]
}) {
  const [open, setOpen] = useState(true)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <button className="flex w-full items-center gap-2 rounded-lg border p-3 text-left font-medium hover:bg-muted/50">
          {open ? (
            <ChevronDown className="size-4" />
          ) : (
            <ChevronRight className="size-4" />
          )}
          <span>{tenantSlug}</span>
          <span className="text-sm font-normal text-muted-foreground">
            ({users.length} user{users.length !== 1 ? "s" : ""})
          </span>
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="ml-6 mt-2 space-y-2 border-l pl-4">
          {users.map((u) => (
            <UserRow key={u.sub ?? u.username} user={u} tenantSlug={tenantSlug} />
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

function UserRow({ user, tenantSlug }: { user: AdminUserItem; tenantSlug: string | null }) {
  const email = getUserDisplayEmail(user)
  const name = getUserDisplayName(user)

  return (
    <div className="flex items-center justify-between rounded border p-2">
      <div>
        <span className="font-medium">{name || email || user.sub || user.username}</span>
        {email && (
          <span className="ml-2 text-sm text-muted-foreground">{email}</span>
        )}
        <span
          className={`ml-2 inline-flex rounded-full px-2 py-0.5 text-xs ${
            user.type === "tenant_user"
              ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
              : "bg-muted text-muted-foreground"
          }`}
        >
          {user.type}
        </span>
        <span className="ml-2 text-xs text-muted-foreground">({user.role})</span>
      </div>
      {tenantSlug && (
        <Button variant="outline" size="sm" asChild>
          <Link to={`/admin/tenants/${tenantSlug}`}>Administer</Link>
        </Button>
      )}
    </div>
  )
}

export { AdminUsersPage }
