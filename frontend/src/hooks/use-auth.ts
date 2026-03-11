"use client"

import { useCallback, useEffect, useState } from "react"
import { fetchAuthSession, getCurrentUser } from "aws-amplify/auth"

export interface UseAuthResult {
  isAuthenticated: boolean
  loading: boolean
  userId: string | null
  checkAuth: () => Promise<void>
}

/**
 * Returns auth state. Uses fetchAuthSession() which properly rehydrates
 * tokens from localStorage on page reload (getCurrentUser() can throw
 * before Amplify finishes bootstrapping the in-memory auth state).
 */
export function useAuth(): UseAuthResult {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)
  const [userId, setUserId] = useState<string | null>(null)

  const checkAuth = useCallback(async () => {
    setLoading(true)
    try {
      const session = await fetchAuthSession()
      if (session.tokens?.accessToken) {
        setIsAuthenticated(true)
        try {
          const user = await getCurrentUser()
          setUserId(user?.userId ?? null)
        } catch {
          setUserId(null)
        }
      } else {
        setIsAuthenticated(false)
        setUserId(null)
      }
    } catch {
      setIsAuthenticated(false)
      setUserId(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void checkAuth()
  }, [checkAuth])

  return { isAuthenticated, loading, userId, checkAuth }
}
