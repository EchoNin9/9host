import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { FeatureGate } from "@/components/feature-gate"
import { ModuleLocked } from "@/components/module-locked"
import { LoadingState, Notice } from "@/components/page"
import { TenantPage, TenantPageHeader } from "@/components/tenant-page"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantMetadata } from "@/hooks/use-tenant-metadata"
import { useAnalytics } from "@/hooks/use-analytics"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts"

const AXIS_TICK = { fontSize: 11, fill: "var(--muted-foreground)" }
const TOOLTIP_STYLE = {
  background: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: 6,
  color: "var(--popover-foreground)",
  fontSize: 12,
}

function AnalyticsCharts() {
  const { data, loading, error } = useAnalytics()

  if (loading) {
    return <LoadingState label="Loading analytics…" rows={3} />
  }

  if (error || !data) {
    return <Notice tone="danger">{error ?? "Unable to load analytics."}</Notice>
  }

  const { page_views_over_time, total_page_views, unique_visitors, top_pages, placeholder } = data

  return (
    <div className="space-y-6">
      {placeholder && (
        <Notice tone="info" title="Sample data">
          Real traffic numbers appear here once analytics collection is live for your sites.
        </Notice>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        {[
          { label: "Page views", value: total_page_views },
          { label: "Unique visitors", value: unique_visitors },
        ].map((k) => (
          <div key={k.label} className="rounded-lg border bg-card p-5 shadow-card">
            <p className="eyebrow">{k.label} · last 30 days</p>
            <p className="tabular mt-2 text-4xl font-light tracking-tight">{k.value.toLocaleString()}</p>
          </div>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Page views over time</CardTitle>
          <CardDescription>
            Daily page views{placeholder ? " (sample data)" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={page_views_over_time}>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis
                  dataKey="date"
                  tick={AXIS_TICK}
                  tickLine={false}
                  axisLine={{ stroke: "var(--border)" }}
                  tickFormatter={(v) => v.slice(5)}
                  minTickGap={16}
                />
                <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={40} />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  cursor={{ stroke: "var(--border)" }}
                  formatter={(value: unknown) =>
                    typeof value === "number" ? value.toLocaleString() : String(value ?? "")
                  }
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  name="Page views"
                  stroke="var(--chart-1)"
                  fill="var(--chart-1)"
                  fillOpacity={0.12}
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Top pages</CardTitle>
          <CardDescription>Most viewed pages</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={top_pages}
                layout="vertical"
                margin={{ left: 8, right: 16 }}
              >
                <CartesianGrid horizontal={false} stroke="var(--border)" />
                <XAxis type="number" tick={AXIS_TICK} tickLine={false} axisLine={false} />
                <YAxis
                  type="category"
                  dataKey="path"
                  width={110}
                  tick={{ ...AXIS_TICK, fontFamily: "var(--font-mono)" }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  cursor={{ fill: "var(--muted)" }}
                  formatter={(value: unknown) =>
                    typeof value === "number" ? value.toLocaleString() : String(value ?? "")
                  }
                />
                <Bar dataKey="views" name="Views" fill="var(--chart-1)" radius={[0, 3, 3, 0]} barSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function TenantAnalytics() {
  const { tenantSlug } = useTenant()
  const { tenant } = useTenantMetadata()
  const isVip = (tenant?.tier?.toLowerCase() ?? "") === "vip"

  const content = tenantSlug ? <AnalyticsCharts /> : <Notice tone="info">No tenant selected.</Notice>

  return (
    <TenantPage>
      <TenantPageHeader title="Analytics" description="Traffic across all of this tenant’s published sites." />
      {isVip ? (
        content
      ) : (
        <FeatureGate feature="advanced_analytics" fallback={<ModuleLocked feature="advanced_analytics" />}>
          {content}
        </FeatureGate>
      )}
    </TenantPage>
  )
}

export { TenantAnalytics }
