"use client"

import { useTenantScope } from "@/context/tenant-scope"
import { useCallback, useEffect, useRef, useState } from "react"
import { getToken } from "@/lib/api"
import {
  fetchDomains,
  createDomain,
  deleteDomain as deleteDomainApi,
  activateDomain as activateDomainApi,
  type ActivateDomainResponse,
  type Domain,
} from "@/lib/api"

export interface UseDomainsResult {
  domains: Domain[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
  /** Throws with the backend error message on failure. */
  add: (body: { domain: string; site_id: string }) => Promise<Domain>
  remove: (domain: string) => Promise<boolean>
  /** Re-checks Cloudflare status; throws with the backend error message on failure. */
  activate: (domain: string) => Promise<ActivateDomainResponse>
  /** True when any domain has PENDING_VALIDATION status and polling is active */
  polling: boolean
}

/**
 * Fetches and mutates custom domains for the current tenant (Pro+ tier).
 */
/** Polling interval for PENDING_VALIDATION domains (10 seconds). */
const POLL_INTERVAL = 10_000
/** Stop polling after 30 minutes. */
const POLL_MAX_DURATION = 30 * 60 * 1000

export function useDomains(): UseDomainsResult {
  const { tenantSlug, api } = useTenantScope()
  const [domains, setDomains] = useState<Domain[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [polling, setPolling] = useState(false)
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollStartRef = useRef<number>(0)

  const load = useCallback(async () => {
    if (!tenantSlug) {
      setDomains([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const list = await fetchDomains(api, token)
      setDomains(list)
    } catch (e) {
      setDomains([])
      setError(e instanceof Error ? e.message : "Failed to load domains")
    } finally {
      setLoading(false)
    }
  }, [tenantSlug, api])

  // Task 2.118: Auto-poll when any domain is PENDING_VALIDATION
  const hasPending = domains.some(
    (d) => d.status?.toUpperCase() === "PENDING_VALIDATION"
  )

  useEffect(() => {
    if (hasPending && !pollTimerRef.current) {
      pollStartRef.current = Date.now()
      setPolling(true)
      pollTimerRef.current = setInterval(async () => {
        if (Date.now() - pollStartRef.current > POLL_MAX_DURATION) {
          // Timeout — stop polling
          if (pollTimerRef.current) clearInterval(pollTimerRef.current)
          pollTimerRef.current = null
          setPolling(false)
          return
        }
        try {
          const token = await getToken()
          const list = await fetchDomains(api, token)
          setDomains(list)
        } catch {
          // ignore polling errors
        }
      }, POLL_INTERVAL)
    }
    if (!hasPending && pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
      setPolling(false)
    }
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
  }, [hasPending, api])

  useEffect(() => {
    void load()
  }, [load])

  const add = useCallback(
    async (body: { domain: string; site_id: string }) => {
      const token = await getToken()
      const domain = await createDomain(api, token, body)
      void load()
      return domain
    },
    [api, load]
  )

  const remove = useCallback(
    async (domain: string) => {
      if (!tenantSlug) return false
      const token = await getToken()
      const ok = await deleteDomainApi(api, token, domain)
      if (ok) void load()
      return ok
    },
    [tenantSlug, api, load]
  )

  const activate = useCallback(
    async (domain: string): Promise<ActivateDomainResponse> => {
      const token = await getToken()
      const result = await activateDomainApi(api, token, domain)
      void load()
      return result
    },
    [api, load]
  )

  return { domains, loading, error, refetch: load, add, remove, activate, polling }
}
