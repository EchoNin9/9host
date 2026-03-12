"use client"

import { useCallback, useEffect, useState } from "react"
import { fetchAuthSession, getCurrentUser } from "aws-amplify/auth"
import { isSiteUser as checkSiteUser } from "@/lib/api"

export interface UseAuthResult {
  isAuthenticated: boolean
  loading: boolean
  userId: string | null
  isSiteUser: boolean
  checkAuth: () => Promise<void>
}

/**
 * Returns auth state. Supports both Cognito and site-login (non-Cognito) users.
 * Site users have isSiteUser=true and are locked to their tenant.
 */
export function useAuth(): UseAuthResult {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)
  const [userId, setUserId] = useState<string | null>(null)
  const [siteUser, setSiteUser] = useState(false)

  const checkAuth = useCallback(async () => {
    setLoading(true)
    try {
      if (checkSiteUser()) {
        setIsAuthenticated(true)
        setUserId(null)
        setSiteUser(true)
        setLoading(false)
        return
      }
      const session = await fetchAuthSession()
      if (session.tokens?.accessToken) {
        setIsAuthenticated(true)
        setSiteUser(false)
        try {
          const user = await getCurrentUser()
          setUserId(user?.userId ?? null)
        } catch {
          setUserId(null)
        }
      } else {
        setIsAuthenticated(false)
        setUserId(null)
        setSiteUser(false)
      }
    } catch {
      setIsAuthenticated(false)
      setUserId(null)
      setSiteUser(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void checkAuth()
  }, [checkAuth])

  return { isAuthenticated, loading, userId, isSiteUser: siteUser, checkAuth }
}
