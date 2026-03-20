/**
 * Visual card-based template picker (Task 1.7).
 *
 * Replaces the plain <select> dropdown with clickable cards
 * showing SVG thumbnails, template name, description, and tier badge.
 */

import { Check } from "lucide-react"
import { getTemplateThumbnail, BlankSiteThumb } from "@/components/template-thumbnails"
import type { Template } from "@/lib/api"

const TIER_COLORS: Record<string, string> = {
  FREE: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
  PRO: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  BUSINESS: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
  VIP: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
}

interface TemplatePickerProps {
  templates: Template[]
  value: string
  onChange: (slug: string) => void
}

export function TemplatePicker({ templates, value, onChange }: TemplatePickerProps) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {/* Blank site option */}
      <button
        type="button"
        onClick={() => onChange("")}
        className={`group relative flex flex-col overflow-hidden rounded-lg border-2 text-left transition-colors ${
          value === ""
            ? "border-primary ring-2 ring-primary/20"
            : "border-muted hover:border-muted-foreground/30"
        }`}
      >
        <div className="aspect-[10/7] w-full bg-muted/30 p-1">
          <BlankSiteThumb />
        </div>
        <div className="flex flex-1 flex-col gap-0.5 p-2">
          <span className="text-xs font-medium">Blank site</span>
          <span className="text-[10px] leading-tight text-muted-foreground">
            Start from scratch
          </span>
        </div>
        {value === "" && (
          <div className="absolute right-1.5 top-1.5 rounded-full bg-primary p-0.5 text-primary-foreground">
            <Check className="size-3" />
          </div>
        )}
      </button>

      {/* Template cards */}
      {templates.map((t) => {
        const selected = value === t.slug
        const tierClass = TIER_COLORS[t.tier_required] ?? TIER_COLORS.FREE
        return (
          <button
            key={t.slug}
            type="button"
            onClick={() => onChange(t.slug)}
            className={`group relative flex flex-col overflow-hidden rounded-lg border-2 text-left transition-colors ${
              selected
                ? "border-primary ring-2 ring-primary/20"
                : "border-muted hover:border-muted-foreground/30"
            }`}
          >
            <div className="aspect-[10/7] w-full bg-muted/30 p-1">
              {getTemplateThumbnail(t.slug)}
            </div>
            <div className="flex flex-1 flex-col gap-0.5 p-2">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-medium">{t.name}</span>
                {t.tier_required !== "FREE" && (
                  <span className={`inline-flex rounded px-1 py-0.5 text-[9px] font-semibold leading-none ${tierClass}`}>
                    {t.tier_required}
                  </span>
                )}
                {t.is_custom && (
                  <span className="inline-flex rounded bg-muted px-1 py-0.5 text-[9px] font-semibold leading-none text-muted-foreground">
                    Custom
                  </span>
                )}
              </div>
              <span className="line-clamp-2 text-[10px] leading-tight text-muted-foreground">
                {t.description}
              </span>
            </div>
            {selected && (
              <div className="absolute right-1.5 top-1.5 rounded-full bg-primary p-0.5 text-primary-foreground">
                <Check className="size-3" />
              </div>
            )}
          </button>
        )
      })}
    </div>
  )
}
