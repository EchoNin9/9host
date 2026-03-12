"use client"

import { useCallback, useEffect, useState } from "react"
import { getToken } from "@/lib/api"
import { fetchTenants, type Tenant } from "@/lib/api"

export interface UseTenantsResult {
  tenants: Tenant[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

/**
 * Fetches tenant list from /api/tenants using Cognito access token.
 * Returns empty array when unauthenticated or on error.
 */
export function useTenants(): UseTenantsResult {
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const list = await fetchTenants(token)
      setTenants(list)
    } catch (e) {
      setTenants([])
      setError(e instanceof Error ? e.message : "Failed to load tenants")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return { tenants, loading, error, refetch: load }
}
