/**
 * Page-level layout primitives shared by the Tenant Dashboard and the Superadmin Console (T-30):
 * one page width, one header pattern, and one look for empty / loading / notice states.
 */

import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { AlertTriangle, ArrowLeft, CheckCircle2, Info, XCircle, type LucideIcon } from "lucide-react"

import { Skeleton } from "@/components/ui/skeleton"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

/** Padding + max width for a standalone page inside the app shell. */
export const PAGE_CLASSES = "mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8"

export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <div data-slot="page" className={cn("flex flex-1 flex-col gap-6", PAGE_CLASSES, className)}>{children}</div>
}

export interface PageHeaderProps {
  title: ReactNode
  description?: ReactNode
  /** Small mono label above the title (section or object type). */
  eyebrow?: ReactNode
  /** Right-aligned actions; the primary action goes last. */
  actions?: ReactNode
  /** Back link rendered above the title. */
  back?: { to: string; label: string }
  /** Badges / meta rendered beside the title. */
  meta?: ReactNode
  as?: "h1" | "h2"
  className?: string
}

export function PageHeader({ title, description, eyebrow, actions, back, meta, as = "h1", className }: PageHeaderProps) {
  const Heading = as
  return (
    <header className={cn("flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between", className)}>
      <div className="min-w-0 space-y-1.5">
        {back && (
          <Link
            to={back.to}
            className="mb-2 inline-flex items-center gap-1 rounded-sm text-sm text-muted-foreground hover:text-foreground sm:hidden"
          >
            <ArrowLeft className="size-3.5" aria-hidden />
            {back.label}
          </Link>
        )}
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <Heading
            className={cn(
              "font-semibold tracking-tight text-foreground",
              as === "h1" ? "text-2xl" : "text-xl"
            )}
          >
            {title}
          </Heading>
          {meta}
        </div>
        {description && <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon?: LucideIcon
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed bg-card/60 px-6 py-12 text-center",
        className
      )}
    >
      {Icon && (
        <span className="flex size-10 items-center justify-center rounded-lg border bg-card text-muted-foreground shadow-card">
          <Icon className="size-5" aria-hidden />
        </span>
      )}
      <div className="space-y-1">
        <p className="font-medium text-foreground">{title}</p>
        {description && <p className="mx-auto max-w-sm text-sm text-muted-foreground">{description}</p>}
      </div>
      {action && <div className="mt-1 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  )
}

/** Skeleton placeholder rows; announces itself to screen readers. */
export function LoadingState({ label = "Loading…", rows = 3, className }: { label?: string; rows?: number; className?: string }) {
  return (
    <div role="status" aria-busy="true" className={cn("space-y-2", className)}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-14 w-full" style={{ opacity: 1 - i * 0.2 }} />
      ))}
    </div>
  )
}

const NOTICE_TONES = {
  info: { icon: Info, cls: "border-info/25 bg-info/5 text-foreground [&>svg]:text-info" },
  success: { icon: CheckCircle2, cls: "border-success/25 bg-success/5 text-foreground [&>svg]:text-success" },
  warning: { icon: AlertTriangle, cls: "border-warning/30 bg-warning/5 text-foreground [&>svg]:text-warning" },
  danger: { icon: XCircle, cls: "border-danger/25 bg-danger/5 text-foreground [&>svg]:text-danger" },
} as const

export function Notice({
  tone = "info",
  title,
  children,
  action,
  className,
}: {
  tone?: keyof typeof NOTICE_TONES
  title?: ReactNode
  children?: ReactNode
  action?: ReactNode
  className?: string
}) {
  const { icon: Icon, cls } = NOTICE_TONES[tone]
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn("flex items-start gap-3 rounded-lg border px-4 py-3 text-sm", cls, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1 space-y-0.5">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className="text-muted-foreground [&_a]:text-foreground">{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

/** Label + control + hint/error, consistently spaced. */
export function FormField({
  label,
  htmlFor,
  hint,
  error,
  children,
  className,
}: {
  label: ReactNode
  htmlFor?: string
  hint?: ReactNode
  error?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  )
}
