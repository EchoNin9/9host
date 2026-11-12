/** Centered single-card layout for sign-in, sign-up, confirmation and tenant picking (T-30). */

import type { ReactNode } from "react"
import type { LucideIcon } from "lucide-react"

import { BrandMark } from "@/components/app-shell"
import { cn } from "@/lib/utils"

export function AuthLayout({
  title,
  description,
  icon: Icon,
  children,
  footer,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  icon?: LucideIcon
  children: ReactNode
  footer?: ReactNode
  className?: string
}) {
  return (
    <div className="flex min-h-svh flex-col bg-sidebar px-4 py-10 sm:py-16">
      <div className={cn("mx-auto flex w-full max-w-sm flex-1 flex-col", className)}>
        <div className="mb-8 flex items-center gap-2.5">
          <BrandMark />
          <span className="leading-tight">
            <span className="block text-sm font-semibold">Echo9</span>
            <span className="block font-mono text-[0.6875rem] text-muted-foreground">console · 9host</span>
          </span>
        </div>
        <main className="rounded-lg border bg-card p-6 shadow-raised sm:p-7">
          {Icon && (
            <span className="mb-4 flex size-9 items-center justify-center rounded-md bg-brand-muted text-primary">
              <Icon className="size-5" aria-hidden />
            </span>
          )}
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          {description && <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>}
          <div className="mt-6">{children}</div>
        </main>
        {footer && <div className="mt-6 space-y-2 text-center text-sm text-muted-foreground">{footer}</div>}
      </div>
    </div>
  )
}

export function FullScreenLoading({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="flex min-h-svh items-center justify-center gap-3 bg-sidebar text-sm text-muted-foreground">
      <span className="size-4 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" aria-hidden />
      {label}
    </div>
  )
}
