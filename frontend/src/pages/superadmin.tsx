"use client"

import { Link, Navigate, useNavigate } from "react-router-dom"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { useAuth } from "@/hooks/use-auth"
import { useImpersonation } from "@/hooks/use-impersonation"
import { UserCog } from "lucide-react"

function SuperadminPage() {
  const { isAuthenticated, loading: authLoading } = useAuth()
  const { tenants, loading, isSuperadmin } = useAdminTenants()
  const { setImpersonate } = useImpersonation()
  const navigate = useNavigate()

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="text-muted-foreground">Loading…</span>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (!loading && !isSuperadmin) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Access denied</CardTitle>
            <CardDescription>
              Superadmin access required. You do not have permission to view this
              page.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="secondary">
              <Link to="/">Back to platform</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const handleImpersonate = (slug: string) => {
    setImpersonate(slug)
    navigate(`/${slug}`)
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-8">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <div className="flex items-center gap-2">
            <UserCog className="size-6" />
            <CardTitle>Superadmin — All Tenants</CardTitle>
          </div>
          <CardDescription>
            Platform admin view. Impersonate a tenant to act as them.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading tenants…</p>
          ) : tenants.length === 0 ? (
            <p className="text-sm text-muted-foreground">No tenants yet.</p>
          ) : (
            <ul className="space-y-2">
              {tenants.map((t) => (
                <li
                  key={t.slug}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div>
                    <span className="font-medium">{t.name || t.slug}</span>
                    <span className="ml-2 text-sm text-muted-foreground">
                      ({t.slug}) · {t.tier}
                    </span>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleImpersonate(t.slug)}
                  >
                    Impersonate
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-4">
            <Button asChild variant="link" className="p-0">
              <Link to="/">← Back to platform</Link>
            </Button>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

export { SuperadminPage }
