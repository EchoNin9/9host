"use client"

import { useCallback, useEffect, useState } from "react"
import { fetchAuthSession } from "aws-amplify/auth"
import { fetchAnalytics, type AnalyticsResponse } from "@/lib/api"

export interface UseAnalyticsResult {
  data: AnalyticsResponse | null
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

/**
 * Fetches analytics for the current tenant from /api/tenant/analytics.
 * Requires Pro+ tier (API returns 403 for Free).
 */
export function useAnalytics(tenantSlug: string | null): UseAnalyticsResult {
  const [data, setData] = useState<AnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!tenantSlug) {
      setData(null)
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const result = await fetchAnalytics(tenantSlug, token)
      setData(result)
    } catch (e) {
      setData(null)
      setError(e instanceof Error ? e.message : "Failed to load analytics")
    } finally {
      setLoading(false)
    }
  }, [tenantSlug])

  useEffect(() => {
    void load()
  }, [load])

  return { data, loading, error, refetch: load }
}
