/**
 * Live Edge Routing & Domains Health (9host-site-hosts-kvs) — Superadmin Console only.
 * Mounted solely under /admin (SuperadminLayout guard) and backed by GET /api/admin/edge-kvs
 * (require_superadmin). Never render tenant domain lists or KVS entries elsewhere.
 */

import { useCallback, useEffect, useState } from "react"
import { RefreshCw } from "lucide-react"
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { LoadingState, Notice, Page, PageHeader } from "@/components/page"
import { fetchEdgeKvs, getToken, type EdgeKvsResponse } from "@/lib/api"

function StatusPill({ value }: { value?: string | null }) {
  const v = (value ?? "").toLowerCase()
  return (
    <Badge tone={v === "active" ? "success" : v ? "warning" : "neutral"} dot={v === "active"}>
      {value || "—"}
    </Badge>
  )
}

function AdminEdgeHealthPage() {
  const [data, setData] = useState<EdgeKvsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const result = await fetchEdgeKvs(await getToken("cognito"))
    if (result.ok) setData(result.data)
    else setError(result.error)
    setLoading(false)
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <Page>
      <PageHeader
        eyebrow="Platform"
        title="Edge routing & domains health"
        description={
          <>
            Live hostname routing from <code className="font-mono text-foreground">9host-site-hosts-kvs</code> and
            Cloudflare for SaaS custom-domain status. Superadmin only.
          </>
        }
        actions={
          <Button variant="outline" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      {error ? (
        <Notice tone="danger">{error}</Notice>
      ) : loading && !data ? (
        <LoadingState label="Loading edge routing…" />
      ) : (
        <>
          <Card className="gap-0 py-0">
            <CardHeader className="border-b py-4">
              <CardTitle>
                Live edge routing table{" "}
                <span className="tabular font-normal text-muted-foreground">{data?.entries.length ?? 0}</span>
              </CardTitle>
              <CardDescription>Hostname → tenant / site served at the edge.</CardDescription>
            </CardHeader>
            {!data?.entries.length ? (
              <p className="px-5 py-6 text-sm text-muted-foreground">No hostnames are routed at the edge yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>Hostname</TableHead>
                    <TableHead>Tenant</TableHead>
                    <TableHead>Site</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.entries.map((e) => (
                    <TableRow key={e.hostname}>
                      <TableCell className="font-mono">{e.hostname}</TableCell>
                      <TableCell>{e.tenant}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{e.site_id}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>

          <Card className="gap-0 py-0">
            <CardHeader className="border-b py-4">
              <CardTitle>
                Custom domains health{" "}
                <span className="tabular font-normal text-muted-foreground">{data?.domains.length ?? 0}</span>
              </CardTitle>
              <CardDescription>Cloudflare for SaaS hostname and SSL status across tenants.</CardDescription>
            </CardHeader>
            {!data?.domains.length ? (
              <p className="px-5 py-6 text-sm text-muted-foreground">No custom domains registered.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>Domain</TableHead>
                    <TableHead>Tenant</TableHead>
                    <TableHead>Site</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Hostname</TableHead>
                    <TableHead>SSL</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.domains.map((d) => (
                    <TableRow key={d.domain}>
                      <TableCell className="font-mono">{d.domain}</TableCell>
                      <TableCell>{d.tenant_slug}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{d.site_id}</TableCell>
                      <TableCell><StatusPill value={d.status} /></TableCell>
                      <TableCell><StatusPill value={d.cf_status} /></TableCell>
                      <TableCell><StatusPill value={d.ssl_status} /></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>
        </>
      )}
    </Page>
  )
}

export { AdminEdgeHealthPage }
