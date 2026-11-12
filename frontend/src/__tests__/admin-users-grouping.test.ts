import { describe, it, expect } from "vitest"
import { groupAdminUsers } from "@/lib/admin-users"
import type { AdminUserItem } from "@/lib/api"

const adam: AdminUserItem = {
  type: "cognito",
  sub: "sub-adam",
  email: "adam@echo9.net",
  name: "",
  role: "superadmin",
  is_superadmin: true,
}
const drift: AdminUserItem = { type: "cognito", sub: "sub-drift", email: "drift@example.com", role: null }
const owner: AdminUserItem = { type: "cognito", sub: "owner-1", email: "o@acme.test", role: "admin" }

describe("groupAdminUsers", () => {
  it("keeps platform admins out of orphaned", () => {
    const g = groupAdminUsers({
      platform_admins: [adam],
      users_by_tenant: { acme: [owner] },
      orphaned: [drift, { ...adam, role: null, is_superadmin: undefined }],
    })
    expect(g.platformAdmins).toEqual([adam])
    expect(g.orphaned).toEqual([drift])
    expect(g.usersByTenant).toEqual({ acme: [owner] })
  })

  it("promotes orphaned users flagged is_superadmin when platform_admins is absent", () => {
    const g = groupAdminUsers({ users_by_tenant: {}, orphaned: [drift, adam] })
    expect(g.platformAdmins).toEqual([adam])
    expect(g.orphaned).toEqual([drift])
  })

  it("handles a null response", () => {
    expect(groupAdminUsers(null)).toEqual({ platformAdmins: [], usersByTenant: {}, orphaned: [] })
  })
})
