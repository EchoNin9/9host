"use client"

import { useEffect, useState, useMemo } from "react"
import { Link } from "react-router-dom"
import { getToken } from "@/lib/api"
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
import { groupAdminUsers } from "@/lib/admin-users"
import { ArrowDownAZ, ChevronDown, ChevronRight, ShieldCheck, UserRound } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { LoadingState, Page, PageHeader } from "@/components/page"

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
      const token = await getToken()
      const d = await fetchAdminUsers(token)
      setData(d ?? { users_by_tenant: {}, orphaned: [] })
      setLoading(false)
    }
    void load()
  }, [])

  const grouped = useMemo(() => groupAdminUsers(data), [data])

  const sortedTenantSlugs = useMemo(() => {
    return Object.keys(grouped.usersByTenant).sort((a, b) =>
      sortDir === "a-z" ? a.localeCompare(b) : b.localeCompare(a)
    )
  }, [grouped, sortDir])

  const sortUsers = (users: AdminUserItem[]) => {
    return [...users].sort((a, b) => {
      const emailA = getUserDisplayEmail(a).toLowerCase()
      const emailB = getUserDisplayEmail(b).toLowerCase()
      return sortDir === "a-z"
        ? emailA.localeCompare(emailB)
        : emailB.localeCompare(emailA)
    })
  }

  const header = (
    <PageHeader
      eyebrow="Platform"
      title="Users"
      description="Platform admins first, then every user grouped by tenant."
      actions={
        <Button
          variant="outline"
          onClick={() => setSortDir((d) => (d === "a-z" ? "z-a" : "a-z"))}
          aria-label={`Sort ${sortDir === "a-z" ? "Z to A" : "A to Z"}`}
        >
          <ArrowDownAZ className="size-4" />
          {sortDir === "a-z" ? "A–Z" : "Z–A"}
        </Button>
      }
    />
  )

  if (loading) {
    return (
      <Page>
        {header}
        <LoadingState label="Loading users…" />
      </Page>
    )
  }

  return (
    <Page>
      {header}

      {grouped.platformAdmins.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="size-5" />
              Platform admins ({grouped.platformAdmins.length})
            </CardTitle>
            <CardDescription>
              Members of the Cognito superadmin group. They manage the whole platform, above tenant
              admins and site owners.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {sortUsers(grouped.platformAdmins).map((u) => (
              <UserRow key={u.sub ?? u.username} user={u} tenantSlug={null} />
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Users by tenant</CardTitle>
          <CardDescription>
            Expand each tenant to see users. Orphaned users have no tenant.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          {sortedTenantSlugs.map((slug) => (
            <TenantUserGroup
              key={slug}
              tenantSlug={slug}
              users={sortUsers(grouped.usersByTenant[slug] ?? [])}
            />
          ))}

          {grouped.orphaned.length > 0 && (
            <Collapsible defaultOpen>
              <CollapsibleTrigger asChild>
                <button className="flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-left font-medium hover:bg-accent">
                  <UserRound className="size-4 text-muted-foreground" />
                  Orphaned users
                  <span className="tabular ml-auto text-xs font-normal text-muted-foreground">
                    {grouped.orphaned.length}
                  </span>
                </button>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="mt-1 mb-2 ml-5 space-y-1 border-l pl-3">
                  {sortUsers(grouped.orphaned).map((u) => (
                    <UserRow key={u.sub ?? u.username} user={u} tenantSlug={null} />
                  ))}
                </div>
              </CollapsibleContent>
            </Collapsible>
          )}

          {sortedTenantSlugs.length === 0 && grouped.orphaned.length === 0 && (
            <p className="text-sm text-muted-foreground">No users yet.</p>
          )}
        </CardContent>
      </Card>
    </Page>
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
        <button className="flex w-full items-center gap-2 rounded-md px-3 py-2.5 text-left font-medium hover:bg-accent">
          {open ? (
            <ChevronDown className="size-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground" />
          )}
          <span className="font-mono text-sm">{tenantSlug}</span>
          <span className="tabular ml-auto text-xs font-normal text-muted-foreground">
            {users.length} user{users.length !== 1 ? "s" : ""}
          </span>
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-1 mb-2 ml-5 space-y-1 border-l pl-3">
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
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-md px-2 py-2 hover:bg-muted/50">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{name || email || user.sub || user.username}</p>
        {email && email !== name && <p className="truncate text-xs text-muted-foreground">{email}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {user.is_superadmin && (
          <Badge tone="danger" mono>
            <ShieldCheck aria-hidden />
            superadmin
          </Badge>
        )}
        {user.role && !(user.is_superadmin && user.role === "superadmin") && <Badge>{user.role}</Badge>}
        <Badge mono tone={user.type === "tenant_user" ? "info" : "neutral"}>
          {user.type === "tenant_user" ? "site login" : user.type === "cognito" ? "account" : user.type}
        </Badge>
      </div>
      {tenantSlug && (
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/admin/tenants/${tenantSlug}`}>Administer</Link>
        </Button>
      )}
    </div>
  )
}

export { AdminUsersPage }
