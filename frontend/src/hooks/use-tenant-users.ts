"use client"

import { useCallback, useEffect, useState } from "react"
import { fetchAuthSession } from "aws-amplify/auth"
import {
  fetchTenantUsers,
  fetchUserPermissions,
  updateUserPermissions as updateUserPermissionsApi,
  type TenantUser,
  type ModulePermissions,
} from "@/lib/api"

export interface UseTenantUsersResult {
  users: TenantUser[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

/**
 * Fetches tenant users from /api/tenant/users (admin/manager only).
 */
export function useTenantUsers(tenantSlug: string | null): UseTenantUsersResult {
  const [users, setUsers] = useState<TenantUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!tenantSlug) {
      setUsers([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const list = await fetchTenantUsers(tenantSlug, token)
      setUsers(list)
    } catch (e) {
      setUsers([])
      setError(e instanceof Error ? e.message : "Failed to load users")
    } finally {
      setLoading(false)
    }
  }, [tenantSlug])

  useEffect(() => {
    void load()
  }, [load])

  return { users, loading, error, refetch: load }
}

export interface UseUserPermissionsResult {
  permissions: ModulePermissions | null
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
  update: (perms: Partial<ModulePermissions>) => Promise<boolean>
}

/**
 * Fetches and updates user permissions (admin/manager only).
 */
export function useUserPermissions(
  tenantSlug: string | null,
  userSub: string | null
): UseUserPermissionsResult {
  const [permissions, setPermissions] = useState<ModulePermissions | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!tenantSlug || !userSub) {
      setPermissions(null)
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const perms = await fetchUserPermissions(tenantSlug, token, userSub)
      setPermissions(perms)
    } catch (e) {
      setPermissions(null)
      setError(e instanceof Error ? e.message : "Failed to load permissions")
    } finally {
      setLoading(false)
    }
  }, [tenantSlug, userSub])

  useEffect(() => {
    void load()
  }, [load])

  const update = useCallback(
    async (perms: Partial<ModulePermissions>) => {
      if (!tenantSlug || !userSub) return false
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString() ?? null
      const result = await updateUserPermissionsApi(
        tenantSlug,
        token,
        userSub,
        perms
      )
      if (result) {
        setPermissions(result)
        return true
      }
      return false
    },
    [tenantSlug, userSub]
  )

  return { permissions, loading, error, refetch: load, update }
}
