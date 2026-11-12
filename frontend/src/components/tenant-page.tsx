/**
 * Page shell for tenant resource views. Standalone (Tenant Dashboard) they own the page:
 * padding + <h1>. Embedded in the Superadmin Console tabs (TenantScopeProvider `embedded`)
 * the console already pads the page and owns the <h1>, so they render unpadded with an <h2>.
 */

import { useContext, type ReactNode } from "react"
import { TenantScopeContext } from "@/context/tenant-scope-context"
import { PAGE_CLASSES, PageHeader, type PageHeaderProps } from "@/components/page"
import { cn } from "@/lib/utils"

function useEmbedded(): boolean {
  return useContext(TenantScopeContext)?.embedded ?? false
}

export function TenantPage({ children, className }: { children: ReactNode; className?: string }) {
  const embedded = useEmbedded()
  return (
    <div
      data-slot="tenant-page"
      data-embedded={embedded ? "true" : undefined}
      className={cn("flex flex-1 flex-col gap-6", !embedded && PAGE_CLASSES, className)}
    >
      {children}
    </div>
  )
}

export function TenantPageTitle({ children, className }: { children: ReactNode; className?: string }) {
  const embedded = useEmbedded()
  const Heading = embedded ? "h2" : "h1"
  return (
    <Heading className={cn(embedded ? "text-xl" : "text-2xl", "font-semibold tracking-tight", className)}>
      {children}
    </Heading>
  )
}

/** PageHeader whose heading level follows the embedded/standalone context. */
export function TenantPageHeader(props: Omit<PageHeaderProps, "as">) {
  const embedded = useEmbedded()
  return <PageHeader {...props} as={embedded ? "h2" : "h1"} />
}
