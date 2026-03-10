"use client"

import { useContext } from "react"
import { ImpersonationContext } from "@/contexts/impersonation-context"

export function useImpersonation() {
  const ctx = useContext(ImpersonationContext)
  if (!ctx) {
    return {
      impersonateTenant: null,
      setImpersonate: () => {},
      clearImpersonate: () => {},
      isImpersonating: false,
    }
  }
  return {
    ...ctx,
    isImpersonating: ctx.impersonateTenant !== null,
  }
}
