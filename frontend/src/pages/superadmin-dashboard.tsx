"use client"

import { useEffect, useState } from "react"
import { fetchAuthSession } from "aws-amplify/auth"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { fetchAdminStats, type AdminStats } from "@/lib/api"
import { Users } from "lucide-react"

function SuperadminDashboard() {
  const { tenants, loading } = useAdminTenants()
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [statsLoading, setStatsLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const s = await fetchAdminStats(token)
      setStats(s)
      setStatsLoading(false)
    }
    void load()
  }, [])

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Platform Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of the 9host platform.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Tenants</CardTitle>
            <Users className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {loading ? "..." : tenants.length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
            <Users className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {statsLoading ? "..." : (stats?.total_users ?? 0)}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export { SuperadminDashboard }
