"use client"

import { useCallback, useEffect, useState } from "react"
import { getToken } from "@/lib/api"
import {
  fetchTenantUsers,
  fetchTenantTUsers,
  fetchTenantRoles,
  fetchUserPermissions,
  updateUserPermissions as updateUserPermissionsApi,
  type TenantUser,
  type TenantTUser,
  type TenantRole,
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
      const token = await getToken()
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
      const token = await getToken()
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
      const token = await getToken()
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

export interface UseTenantTUsersResult {
  tusers: TenantTUser[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

/**
 * Fetches non-Cognito tenant users from /api/tenant/tusers (admin/manager only).
 */
export function useTenantTUsers(tenantSlug: string | null): UseTenantTUsersResult {
  const [tusers, setTusers] = useState<TenantTUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!tenantSlug) {
      setTusers([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const list = await fetchTenantTUsers(tenantSlug, token)
      setTusers(list)
    } catch (e) {
      setTusers([])
      setError(e instanceof Error ? e.message : "Failed to load tenant users")
    } finally {
      setLoading(false)
    }
  }, [tenantSlug])

  useEffect(() => {
    void load()
  }, [load])

  return { tusers, loading, error, refetch: load }
}

export interface UseTenantRolesResult {
  roles: TenantRole[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

/**
 * Fetches custom roles from /api/tenant/roles (admin/manager only).
 */
export function useTenantRoles(tenantSlug: string | null): UseTenantRolesResult {
  const [roles, setRoles] = useState<TenantRole[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!tenantSlug) {
      setRoles([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const list = await fetchTenantRoles(tenantSlug, token)
      setRoles(list)
    } catch (e) {
      setRoles([])
      setError(e instanceof Error ? e.message : "Failed to load roles")
    } finally {
      setLoading(false)
    }
  }, [tenantSlug])

  useEffect(() => {
    void load()
  }, [load])

  return { roles, loading, error, refetch: load }
}
