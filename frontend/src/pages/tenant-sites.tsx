import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useTenant } from "@/hooks/use-tenant"

function TenantSites() {
  const { tenantSlug } = useTenant()

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Sites</h1>
        <p className="text-muted-foreground">
          Manage websites for {tenantSlug}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Your sites</CardTitle>
          <CardDescription>Create and manage hosted websites</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No sites yet. Create your first site to get started.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

export { TenantSites }
