"use client"

import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { fetchAuthSession } from "aws-amplify/auth"
import { ArrowRight, Building2, Layers, RadioTower, UserRound } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Page, PageHeader } from "@/components/page"
import { tierLabel } from "@/lib/site-format"
import { useAdminTenants } from "@/hooks/use-admin-tenants"
import { fetchAdminStats, type AdminStats } from "@/lib/api"

const TIERS = ["FREE", "PRO", "BUSINESS", "VIP"] as const
const TIER_FILL: Record<(typeof TIERS)[number], string> = {
  FREE: "bg-chart-3",
  PRO: "bg-chart-1",
  BUSINESS: "bg-chart-2",
  VIP: "bg-chart-4",
}

function Kpi({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return (
    <div className="rounded-lg border bg-card p-4 shadow-card">
      <p className="eyebrow">{label}</p>
      <p className="tabular mt-2 text-3xl font-light tracking-tight">{value}</p>
      {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
    </div>
  )
}

const LINKS = [
  { to: "/admin/tenants", icon: Building2, title: "Tenants", body: "Create, administer, impersonate or delete tenants." },
  { to: "/admin/users", icon: UserRound, title: "Users", body: "Every account and site login, grouped by tenant." },
  { to: "/admin/templates", icon: Layers, title: "Templates", body: "Platform site templates and their tiers." },
  { to: "/admin/edge", icon: RadioTower, title: "Edge & domains", body: "Live hostname routing and custom-domain health." },
]

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

  const byTier = useMemo(() => {
    const counts: Record<string, number> = { FREE: 0, PRO: 0, BUSINESS: 0, VIP: 0 }
    for (const t of tenants) {
      const k = (t.tier ?? "FREE").toUpperCase()
      counts[k] = (counts[k] ?? 0) + 1
    }
    return counts
  }, [tenants])
  const total = tenants.length
  const paid = byTier.PRO + byTier.BUSINESS

  return (
    <Page>
      <PageHeader eyebrow="Platform" title="Dashboard" description="The 9host platform at a glance." />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="Tenants" value={loading ? "–" : total} detail={loading ? undefined : `${paid} on a paid tier`} />
        <Kpi label="Users" value={statsLoading ? "–" : (stats?.total_users ?? 0)} detail="accounts + site logins" />
        <Kpi
          label="Accounts"
          value={statsLoading ? "–" : (stats?.total_cognito_users ?? 0)}
          detail="sign in with email"
        />
        <Kpi
          label="Site logins"
          value={statsLoading ? "–" : (stats?.total_tenant_users ?? 0)}
          detail="tenant-managed users"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <Card>
          <CardHeader>
            <CardTitle>Tenants by tier</CardTitle>
            <CardDescription>Share of all tenants.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted"
              role="img"
              aria-label={TIERS.map((t) => `${tierLabel(t)} ${byTier[t]}`).join(", ")}
            >
              {total > 0 &&
                TIERS.map((t) =>
                  byTier[t] > 0 ? (
                    <span key={t} className={TIER_FILL[t]} style={{ width: `${(byTier[t] / total) * 100}%` }} />
                  ) : null
                )}
            </div>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4">
              {TIERS.map((t) => (
                <div key={t} className="flex items-center gap-2">
                  <span aria-hidden className={`size-2.5 rounded-sm ${TIER_FILL[t]}`} />
                  <dt className="text-sm text-muted-foreground">{tierLabel(t)}</dt>
                  <dd className="tabular ml-auto text-sm font-medium">{loading ? "–" : byTier[t]}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>

        <Card className="gap-0 py-0">
          <ul className="divide-y">
            {LINKS.map((l) => (
              <li key={l.to}>
                <Link to={l.to} className="group flex items-center gap-4 px-5 py-4 hover:bg-accent/50">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-md border bg-muted text-muted-foreground">
                    <l.icon className="size-4" aria-hidden />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium">{l.title}</span>
                    <span className="block truncate text-sm text-muted-foreground">{l.body}</span>
                  </span>
                  <ArrowRight
                    className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                    aria-hidden
                  />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </Page>
  )
}

export { SuperadminDashboard }
