import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { FeatureGate } from "@/components/feature-gate"
import { useTenant } from "@/hooks/use-tenant"

function TenantDomains() {
  const { tenantSlug } = useTenant()

  return (
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Domains</h1>
        <p className="text-muted-foreground">
          Custom domains for {tenantSlug} (Pro+)
        </p>
      </div>

      <FeatureGate
        feature="custom_domains"
        fallback={
          <Card>
            <CardHeader>
              <CardTitle>Custom domains</CardTitle>
              <CardDescription>
                Add custom domains to your sites. Requires Pro or Business tier.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Upgrade to Pro to unlock custom domains.
              </p>
            </CardContent>
          </Card>
        }
      >
        <Card>
          <CardHeader>
            <CardTitle>Custom domains</CardTitle>
            <CardDescription>
              Add custom domains to your sites.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Manage custom domains for your tenant.
            </p>
          </CardContent>
        </Card>
      </FeatureGate>
    </div>
  )
}

export { TenantDomains }
