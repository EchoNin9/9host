import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Status pill. Each tone keeps one meaning across the console:
 * success = live/active, warning = pending/needs attention, danger = error/destructive,
 * info = neutral system state, brand = plan/tier emphasis, neutral = everything else.
 */
const badgeVariants = cva(
  "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap [&_svg]:size-3 [&_svg]:shrink-0",
  {
    variants: {
      tone: {
        neutral: "border-border bg-muted text-muted-foreground",
        success: "border-success/25 bg-success/10 text-success",
        warning: "border-warning/30 bg-warning/10 text-warning",
        danger: "border-danger/25 bg-danger/10 text-danger",
        info: "border-info/25 bg-info/10 text-info",
        brand: "border-primary/25 bg-brand-muted text-primary",
      },
      mono: {
        true: "font-mono text-[0.6875rem] tracking-wide uppercase",
        false: "",
      },
    },
    defaultVariants: { tone: "neutral", mono: false },
  }
)

function Badge({
  className,
  tone,
  mono,
  dot = false,
  children,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants> & { dot?: boolean }) {
  return (
    <span data-slot="badge" className={cn(badgeVariants({ tone, mono }), className)} {...props}>
      {dot && <span aria-hidden className="size-1.5 rounded-full bg-current" />}
      {children}
    </span>
  )
}

export { Badge }
