"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { Users } from "lucide-react"

function SuperadminDashboard() {
  const { tenants, loading } = useAdminTenants()

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
      </div>
    </div>
  )
}

export { SuperadminDashboard }
