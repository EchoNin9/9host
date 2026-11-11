/**
 * Live Edge Routing & Domains Health (9host-site-hosts-kvs) — Superadmin Console only.
 * Mounted solely under /admin (SuperadminLayout guard) and backed by GET /api/admin/edge-kvs
 * (require_superadmin). Never render tenant domain lists or KVS entries elsewhere.
 */

import { useCallback, useEffect, useState } from "react"
import { RefreshCw } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { fetchEdgeKvs, getToken, type EdgeKvsResponse } from "@/lib/api"

const th = "px-3 py-2 text-left font-medium text-muted-foreground"
const td = "px-3 py-2"

function StatusPill({ value }: { value?: string | null }) {
  const v = (value ?? "").toLowerCase()
  const tone =
    v === "active"
      ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
      : v
        ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
        : "bg-muted text-muted-foreground"
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tone}`}>{value || "—"}</span>
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
    <div className="flex flex-1 flex-col gap-6 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Edge Routing &amp; Domains Health</h1>
          <p className="text-muted-foreground">
            Live hostname routing from <code>9host-site-hosts-kvs</code> and Cloudflare for SaaS
            custom-domain status. Superadmin only.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={`mr-2 size-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {error ? (
        <Card>
          <CardContent className="pt-6">
            <p role="alert" className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      ) : loading && !data ? (
        <p className="text-sm text-muted-foreground">Loading edge routing…</p>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Live edge routing table</CardTitle>
              <CardDescription>Hostname → tenant / site served at the edge.</CardDescription>
            </CardHeader>
            <CardContent>
              {!data?.entries.length ? (
                <p className="text-sm text-muted-foreground">No hostnames are routed at the edge yet.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="border-b">
                    <tr>
                      <th scope="col" className={th}>Hostname</th>
                      <th scope="col" className={th}>Tenant</th>
                      <th scope="col" className={th}>Site</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.entries.map((e) => (
                      <tr key={e.hostname} className="border-b last:border-0">
                        <td className={`${td} font-mono`}>{e.hostname}</td>
                        <td className={td}>{e.tenant}</td>
                        <td className={`${td} font-mono text-xs`}>{e.site_id}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Custom domains health</CardTitle>
              <CardDescription>Cloudflare for SaaS hostname and SSL status across tenants.</CardDescription>
            </CardHeader>
            <CardContent>
              {!data?.domains.length ? (
                <p className="text-sm text-muted-foreground">No custom domains registered.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="border-b">
                    <tr>
                      <th scope="col" className={th}>Domain</th>
                      <th scope="col" className={th}>Tenant</th>
                      <th scope="col" className={th}>Site</th>
                      <th scope="col" className={th}>Status</th>
                      <th scope="col" className={th}>Hostname</th>
                      <th scope="col" className={th}>SSL</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.domains.map((d) => (
                      <tr key={d.domain} className="border-b last:border-0">
                        <td className={`${td} font-mono`}>{d.domain}</td>
                        <td className={td}>{d.tenant_slug}</td>
                        <td className={`${td} font-mono text-xs`}>{d.site_id}</td>
                        <td className={td}><StatusPill value={d.status} /></td>
                        <td className={td}><StatusPill value={d.cf_status} /></td>
                        <td className={td}><StatusPill value={d.ssl_status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

export { AdminEdgeHealthPage }
