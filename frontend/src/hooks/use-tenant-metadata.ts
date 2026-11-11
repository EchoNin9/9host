"use client"

import { useTenantScope } from "@/context/tenant-scope"
import { useCallback, useEffect, useState } from "react"
import { getToken } from "@/lib/api"
import { fetchTenant, type TenantMetadata } from "@/lib/api"

export interface UseTenantMetadataResult {
  tenant: TenantMetadata | null
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

/**
 * Fetches tenant metadata from GET /api/tenant (name, tier, owner_sub).
 */
export function useTenantMetadata(): UseTenantMetadataResult {
  const { tenantSlug, api } = useTenantScope()
  const [tenant, setTenant] = useState<TenantMetadata | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!tenantSlug) {
      setTenant(null)
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const data = await fetchTenant(api, token)
      setTenant(data)
    } catch (e) {
      setTenant(null)
      setError(e instanceof Error ? e.message : "Failed to load tenant")
    } finally {
      setLoading(false)
    }
  }, [tenantSlug, api])

  useEffect(() => {
    void load()
  }, [load])

  return { tenant, loading, error, refetch: load }
}
