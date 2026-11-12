/** Display helpers shared by tenant and console views (T-30). */

import type { Site } from "@/lib/api"

export function tierLabel(tier?: string | null): string {
  const t = (tier ?? "free").toLowerCase()
  if (t === "vip") return "VIP"
  return t.charAt(0).toUpperCase() + t.slice(1)
}

/** Public URL of a site on the platform subdomain, or null when it has no slug yet. */
export function siteLiveUrl(site: Pick<Site, "slug">): string | null {
  return site.slug ? `https://${site.slug}.echo9.net` : null
}
