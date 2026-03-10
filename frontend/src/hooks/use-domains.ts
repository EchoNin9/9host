"use client"

import { useCallback, useEffect, useState } from "react"
import { fetchAuthSession } from "aws-amplify/auth"
import {
  fetchDomains,
  createDomain,
  deleteDomain as deleteDomainApi,
  type Domain,
} from "@/lib/api"

export interface UseDomainsResult {
  domains: Domain[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
  add: (body: { domain: string; site_id: string; status?: string }) => Promise<Domain | null>
  remove: (domain: string) => Promise<boolean>
}

/**
 * Fetches and mutates custom domains for the current tenant (Pro+ tier).
 */
export function useDomains(tenantSlug: string | null): UseDomainsResult {
  const [domains, setDomains] = useState<Domain[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!tenantSlug) {
      setDomains([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const list = await fetchDomains(tenantSlug, token)
      setDomains(list)
    } catch (e) {
      setDomains([])
      setError(e instanceof Error ? e.message : "Failed to load domains")
    } finally {
      setLoading(false)
    }
  }, [tenantSlug])

  useEffect(() => {
    void load()
  }, [load])

  const add = useCallback(
    async (body: { domain: string; site_id: string; status?: string }) => {
      if (!tenantSlug) return null
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const domain = await createDomain(tenantSlug, token, body)
      if (domain) void load()
      return domain
    },
    [tenantSlug, load]
  )

  const remove = useCallback(
    async (domain: string) => {
      if (!tenantSlug) return false
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const ok = await deleteDomainApi(tenantSlug, token, domain)
      if (ok) void load()
      return ok
    },
    [tenantSlug, load]
  )

  return { domains, loading, error, refetch: load, add, remove }
}
