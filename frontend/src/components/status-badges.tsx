/** Domain-specific badges so every view says "published", "pending" or a tier the same way. */

import { Loader2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { Domain, Site } from "@/lib/api"
import { tierLabel } from "@/lib/site-format"

export function TierBadge({ tier, className }: { tier?: string | null; className?: string }) {
  const t = (tier ?? "free").toLowerCase()
  return (
    <Badge mono tone={t === "free" ? "neutral" : "brand"} className={className}>
      {tierLabel(t)}
    </Badge>
  )
}

export function SiteStatusBadge({ site }: { site: Pick<Site, "status" | "published_version"> }) {
  if (site.status === "published") {
    return (
      <Badge tone="success" dot>
        Live{site.published_version != null ? ` · v${site.published_version}` : ""}
      </Badge>
    )
  }
  return (
    <Badge tone="neutral" dot>
      Draft
    </Badge>
  )
}

export function DomainStatusBadge({ status }: { status: Domain["status"] }) {
  if (status === "ACTIVE") {
    return (
      <Badge tone="success" dot>
        Active
      </Badge>
    )
  }
  return (
    <Badge tone="warning">
      <Loader2 className="animate-spin" aria-hidden />
      Pending validation
    </Badge>
  )
}
