/**
 * Tenant context: provides tenant_slug extracted from the URL.
 *
 * Extraction (aligned with api/middleware.py):
 * 1. Subdomain: acme.echo9.net → acme
 * 2. Path: /acme/... or /{tenant}/... → acme
 *
 * Platform domains (stage.echo9.net, prod.echo9.net, www.echo9.net) have no tenant.
 */

import { createContext } from "react";

const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/;

function isValidSlug(slug: string): boolean {
  if (!slug || typeof slug !== "string") return false;
  const s = slug.trim().toLowerCase();
  return Boolean(SLUG_PATTERN.test(s)) && s.length <= 64;
}

function extractTenantFromHost(hostname: string, domain: string): string | null {
  const host = hostname.toLowerCase();
  const platformHosts = [
    `stage.${domain}`,
    `prod.${domain}`,
    `www.${domain}`,
    domain,
  ];
  if (platformHosts.includes(host)) return null;

  const suffix = `.${domain}`;
  if (host.endsWith(suffix)) {
    const subdomain = host.slice(0, -suffix.length);
    if (subdomain && isValidSlug(subdomain)) return subdomain;
  }
  return null;
}

function extractTenantFromPath(pathname: string): string | null {
  const segments = pathname.split("/").filter(Boolean);
  const first = segments[0];
  if (first && isValidSlug(first)) return first;
  return null;
}

export interface TenantContextValue {
  /** Tenant slug from URL (e.g. acme.echo9.net → "acme"), or null if platform domain */
  tenantSlug: string | null;
  /** Whether we're on a tenant-scoped URL (has tenant) */
  hasTenant: boolean;
  /** Base path for tenant routes: "" when from subdomain, "/{slug}" when from path */
  tenantBasePath: string;
  /** Re-extract tenant from current URL (e.g. after navigation) */
  refresh: () => void;
}

export const TenantContext = createContext<TenantContextValue | null>(null);

export function extractTenantSlug(domain = "echo9.net"): string | null {
  const result = extractTenantWithBasePath(domain);
  return result?.slug ?? null;
}

export function extractTenantWithBasePath(
  domain = "echo9.net"
): { slug: string; basePath: string } | null {
  if (typeof window === "undefined") return null;
  const host = window.location.hostname;
  const path = window.location.pathname;

  const fromHost = extractTenantFromHost(host, domain);
  if (fromHost) return { slug: fromHost, basePath: "" };

  const fromPath = extractTenantFromPath(path);
  if (fromPath) return { slug: fromPath, basePath: `/${fromPath}` };

  return null;
}
