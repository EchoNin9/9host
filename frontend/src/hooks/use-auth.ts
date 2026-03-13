"use client"

import { useCallback, useEffect, useState } from "react"
import { fetchAuthSession, fetchUserAttributes, getCurrentUser } from "aws-amplify/auth"
import { getSiteUserDisplay, isSiteUser as checkSiteUser } from "@/lib/api"

export interface UseAuthResult {
  isAuthenticated: boolean
  loading: boolean
  userId: string | null
  isSiteUser: boolean
  userDisplay: string | null
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
  const [userDisplay, setUserDisplay] = useState<string | null>(null)

  const checkAuth = useCallback(async () => {
    setLoading(true)
    try {
      if (checkSiteUser()) {
        setIsAuthenticated(true)
        setUserId(null)
        setSiteUser(true)
        setUserDisplay(getSiteUserDisplay())
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
          const attrs = await fetchUserAttributes()
          const display =
            attrs.name ?? attrs.given_name ?? attrs.email ?? attrs.preferred_username ?? null
          setUserDisplay(display ?? null)
        } catch {
          setUserId(null)
          setUserDisplay(null)
        }
      } else {
        setIsAuthenticated(false)
        setUserId(null)
        setSiteUser(false)
        setUserDisplay(null)
      }
    } catch {
      setIsAuthenticated(false)
      setUserId(null)
      setSiteUser(false)
      setUserDisplay(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void checkAuth()
  }, [checkAuth])

  return { isAuthenticated, loading, userId, isSiteUser: siteUser, userDisplay, checkAuth }
}
