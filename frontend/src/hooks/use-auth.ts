"use client"

import { useCallback, useEffect, useState } from "react"
import { getCurrentUser } from "aws-amplify/auth"

export interface UseAuthResult {
  isAuthenticated: boolean
  loading: boolean
  userId: string | null
  checkAuth: () => Promise<void>
}

/**
 * Returns auth state. isAuthenticated is true when user has a valid Cognito session.
 * userId is the Cognito sub (for owner checks, etc.).
 */
export function useAuth(): UseAuthResult {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)
  const [userId, setUserId] = useState<string | null>(null)

  const checkAuth = useCallback(async () => {
    setLoading(true)
    try {
      const user = await getCurrentUser()
      setIsAuthenticated(true)
      setUserId(user?.userId ?? null)
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
