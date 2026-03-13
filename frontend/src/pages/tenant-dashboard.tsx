import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useTenant } from "@/hooks/use-tenant"
import { useSites } from "@/hooks/use-sites"
import { useDomains } from "@/hooks/use-domains"
import { useTenantMetadata } from "@/hooks/use-tenant-metadata"

function TenantDashboard() {
  const { tenantSlug } = useTenant()
  const { tenant } = useTenantMetadata(tenantSlug)
  const { sites } = useSites(tenantSlug)
  const { domains } = useDomains(tenantSlug)
  const tierLabel = tenant?.tier === "VIP" ? "VIP" : tenant?.tier ? tenant.tier.charAt(0) + tenant.tier.slice(1).toLowerCase() : "Free"

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome to {tenantSlug}&apos;s admin
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Sites</CardTitle>
            <CardDescription>Manage your hosted websites</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{sites.length} site{sites.length !== 1 ? "s" : ""}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Domains</CardTitle>
            <CardDescription>Custom domains (Pro+)</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{domains.length} domain{domains.length !== 1 ? "s" : ""}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Settings</CardTitle>
            <CardDescription>Tenant configuration</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{tierLabel} tier</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export { TenantDashboard }
