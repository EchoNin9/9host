/**
 * Impersonation context (Task 2.13).
 * Superadmin can impersonate a tenant; API client adds X-Impersonate-Tenant.
 */

import { createContext } from "react"

export interface ImpersonationContextValue {
  /** Tenant slug being impersonated, or null */
  impersonateTenant: string | null
  /** Start impersonating a tenant */
  setImpersonate: (slug: string) => void
  /** Stop impersonating */
  clearImpersonate: () => void
}

export const ImpersonationContext = createContext<ImpersonationContextValue | null>(
  null
)

const STORAGE_KEY = "9host-impersonate"

export function impersonationStorageGet(): string | null {
  if (typeof window === "undefined") return null
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function impersonationStorageSet(slug: string | null): void {
  if (typeof window === "undefined") return
  try {
    if (slug) {
      localStorage.setItem(STORAGE_KEY, slug)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    // ignore
  }
}
