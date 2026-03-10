"use client"

import { useCallback, useEffect, useState } from "react"
import { fetchAuthSession } from "aws-amplify/auth"
import { fetchAllTenants, type AdminTenant } from "@/lib/api"

export interface UseAdminTenantsResult {
  tenants: AdminTenant[]
  loading: boolean
  error: string | null
  isSuperadmin: boolean
  refetch: () => Promise<void>
}

/**
 * Fetches all tenants from /api/admin/tenants (superadmin only).
 * If 403, user is not superadmin — tenants=[], isSuperadmin=false.
 */
export function useAdminTenants(): UseAdminTenantsResult {
  const [tenants, setTenants] = useState<AdminTenant[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isSuperadmin, setIsSuperadmin] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const { tenants: list, isSuperadmin: ok } = await fetchAllTenants(token)
      setTenants(list)
      setIsSuperadmin(ok)
    } catch (e) {
      setTenants([])
      setIsSuperadmin(false)
      setError(e instanceof Error ? e.message : "Failed to load tenants")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return { tenants, loading, error, isSuperadmin, refetch: load }
}
