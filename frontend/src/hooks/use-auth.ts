"use client"

import { useCallback, useEffect, useState } from "react"
import { getCurrentUser } from "aws-amplify/auth"

export interface UseAuthResult {
  isAuthenticated: boolean
  loading: boolean
  checkAuth: () => Promise<void>
}

/**
 * Returns auth state. isAuthenticated is true when user has a valid Cognito session.
 */
export function useAuth(): UseAuthResult {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)

  const checkAuth = useCallback(async () => {
    setLoading(true)
    try {
      await getCurrentUser()
      setIsAuthenticated(true)
    } catch {
      setIsAuthenticated(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void checkAuth()
  }, [checkAuth])

  return { isAuthenticated, loading, checkAuth }
}
