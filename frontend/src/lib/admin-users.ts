import type { AdminUserItem, AdminUsersResponse } from "@/lib/api"

export interface GroupedAdminUsers {
  /** Platform admins (Cognito superadmin group) — shown above tenant groupings. */
  platformAdmins: AdminUserItem[]
  usersByTenant: Record<string, AdminUserItem[]>
  /** Cognito users with no tenant membership who are not platform admins. */
  orphaned: AdminUserItem[]
}

/**
 * Split GET /api/admin/users into platform admins / tenants / orphaned (T-20).
 * Platform admins never appear under orphaned, even if an older API still lists them there.
 */
export function groupAdminUsers(data: AdminUsersResponse | null): GroupedAdminUsers {
  const platformAdmins = [...(data?.platform_admins ?? [])]
  const adminSubs = new Set(platformAdmins.map((u) => u.sub).filter(Boolean))
  const orphaned: AdminUserItem[] = []
  for (const u of data?.orphaned ?? []) {
    if (u.is_superadmin || (u.sub && adminSubs.has(u.sub))) {
      if (!u.sub || !adminSubs.has(u.sub)) {
        platformAdmins.push(u)
        if (u.sub) adminSubs.add(u.sub)
      }
    } else {
      orphaned.push(u)
    }
  }
  return { platformAdmins, usersByTenant: data?.users_by_tenant ?? {}, orphaned }
}
