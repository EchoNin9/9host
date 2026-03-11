"use client"

import { useCallback, useEffect, useState } from "react"
import { fetchAuthSession } from "aws-amplify/auth"
import {
  fetchSites,
  createSite,
  updateSite,
  deleteSite as deleteSiteApi,
  type Site,
} from "@/lib/api"

export interface UseSitesResult {
  sites: Site[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
  create: (body: { name: string; slug?: string; status?: string; template_id?: string }) => Promise<Site | null>
  update: (
    siteId: string,
    body: { name?: string; slug?: string; status?: string }
  ) => Promise<Site | null>
  remove: (siteId: string) => Promise<boolean>
}

/**
 * Fetches and mutates sites for the current tenant.
 */
export function useSites(tenantSlug: string | null): UseSitesResult {
  const [sites, setSites] = useState<Site[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!tenantSlug) {
      setSites([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const list = await fetchSites(tenantSlug, token)
      setSites(list)
    } catch (e) {
      setSites([])
      setError(e instanceof Error ? e.message : "Failed to load sites")
    } finally {
      setLoading(false)
    }
  }, [tenantSlug])

  useEffect(() => {
    void load()
  }, [load])

  const create = useCallback(
    async (body: { name: string; slug?: string; status?: string; template_id?: string }) => {
      if (!tenantSlug) return null
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const site = await createSite(tenantSlug, token, body)
      if (site) void load()
      return site
    },
    [tenantSlug, load]
  )

  const update = useCallback(
    async (
      siteId: string,
      body: { name?: string; slug?: string; status?: string }
    ) => {
      if (!tenantSlug) return null
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const site = await updateSite(tenantSlug, token, siteId, body)
      if (site) void load()
      return site
    },
    [tenantSlug, load]
  )

  const remove = useCallback(
    async (siteId: string) => {
      if (!tenantSlug) return false
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const ok = await deleteSiteApi(tenantSlug, token, siteId)
      if (ok) void load()
      return ok
    },
    [tenantSlug, load]
  )

  return { sites, loading, error, refetch: load, create, update, remove }
}
