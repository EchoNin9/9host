"use client"

import { useCallback, useMemo, useState, type ReactNode } from "react"
import {
  ImpersonationContext,
  impersonationStorageGet,
  impersonationStorageSet,
} from "./impersonation-context"

export interface ImpersonationProviderProps {
  children: ReactNode
}

export function ImpersonationProvider({ children }: ImpersonationProviderProps) {
  const [impersonateTenant, setState] = useState<string | null>(() =>
    impersonationStorageGet()
  )

  const setImpersonate = useCallback((slug: string) => {
    const s = slug.trim().toLowerCase()
    if (s) {
      setState(s)
      impersonationStorageSet(s)
    }
  }, [])

  const clearImpersonate = useCallback(() => {
    setState(null)
    impersonationStorageSet(null)
  }, [])

  const value = useMemo(
    () => ({
      impersonateTenant,
      setImpersonate,
      clearImpersonate,
    }),
    [impersonateTenant, setImpersonate, clearImpersonate]
  )

  return (
    <ImpersonationContext.Provider value={value}>
      {children}
    </ImpersonationContext.Provider>
  )
}
