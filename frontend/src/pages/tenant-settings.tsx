import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantRole } from "@/hooks/use-tenant-role"

function TenantSettings() {
  const { tenantSlug } = useTenant()
  const { role, canEdit } = useTenantRole()

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-muted-foreground">
          Configure {tenantSlug}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tenant settings</CardTitle>
          <CardDescription>
            {canEdit
              ? "Manage your tenant configuration"
              : `View-only access (${role})`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Settings form coming soon.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

export { TenantSettings }
