/**
 * Visual card-based template picker (Task 1.7).
 *
 * Replaces the plain <select> dropdown with clickable cards
 * showing SVG thumbnails, template name, description, and tier badge.
 */

import { Check } from "lucide-react"
import { getTemplateThumbnail, BlankSiteThumb } from "@/components/template-thumbnails"
import type { Template } from "@/lib/api"

import { Badge } from "@/components/ui/badge"
import { TierBadge } from "@/components/status-badges"

const CARD =
  "group relative flex flex-col overflow-hidden rounded-lg border bg-card text-left shadow-card transition-[border-color,box-shadow] hover:border-input focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
const CARD_SELECTED = "border-primary ring-2 ring-primary/25 hover:border-primary"

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
        aria-pressed={value === ""}
        className={`${CARD} ${value === "" ? CARD_SELECTED : ""}`}
      >
        <div className="aspect-[10/7] w-full bg-muted/30 p-1">
          <BlankSiteThumb />
        </div>
        <div className="flex flex-1 flex-col gap-0.5 p-2">
          <span className="text-xs font-medium">Decide later</span>
          <span className="text-xs leading-tight text-muted-foreground">
            No template yet. You need one to publish.
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
        return (
          <button
            key={t.slug}
            type="button"
            onClick={() => onChange(t.slug)}
            aria-pressed={selected}
            className={`${CARD} ${selected ? CARD_SELECTED : ""}`}
          >
            <div className="aspect-[10/7] w-full bg-muted/30 p-1">
              {getTemplateThumbnail(t.slug)}
            </div>
            <div className="flex flex-1 flex-col gap-0.5 p-2">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-xs font-medium">{t.name}</span>
                {t.tier_required !== "FREE" && <TierBadge tier={t.tier_required} className="px-1.5 py-0 text-[0.625rem]" />}
                {t.is_custom && (
                  <Badge mono className="px-1.5 py-0 text-[0.625rem]">
                    Custom
                  </Badge>
                )}
              </div>
              <span className="line-clamp-2 text-xs leading-tight text-muted-foreground">
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
