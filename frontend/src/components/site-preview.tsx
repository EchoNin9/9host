/**
 * Site Previewer (Live Preview) — Task 2.80
 * Renders preview data from GET /api/tenant/sites/{id}/preview
 */

import { useState, useEffect } from "react"
import { ExternalLink, Loader2 } from "lucide-react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { getToken, fetchSitePreview, fetchTemplates, type SitePreviewData, type Template } from "@/lib/api"
import { useTenant } from "@/hooks/use-tenant"

interface SitePreviewProps {
  siteId: string
  siteName: string
  templateId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function PreviewMockup({ preview }: { preview: SitePreviewData }) {
  const pages = preview.components?.pages ?? []
  const sections = preview.components?.sections ?? {}

  return (
    <div className="rounded-lg border bg-muted/30 p-4 font-sans text-sm">
      <div className="mb-4 border-b pb-2">
        <h2 className="text-lg font-semibold">{preview.name}</h2>
        <p className="text-xs text-muted-foreground">
          {preview.template_name ?? preview.template_slug ?? "Template"}
        </p>
      </div>
      <div className="space-y-4">
        {pages.length === 0 ? (
          <p className="text-muted-foreground">No pages defined</p>
        ) : (
          pages.map((page) => (
            <div key={page} className="rounded border bg-background p-3">
              <p className="mb-2 font-medium capitalize">{page}</p>
              <div className="flex flex-wrap gap-1">
                {(sections[page] ?? []).map((sec) => (
                  <span
                    key={sec}
                    className="inline-flex rounded bg-muted px-2 py-0.5 text-xs"
                  >
                    {sec}
                  </span>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export function SitePreview({
  siteId,
  siteName,
  templateId,
  open,
  onOpenChange,
}: SitePreviewProps) {
  const { tenantSlug } = useTenant()
  const [preview, setPreview] = useState<SitePreviewData | null>(null)
  const [templates, setTemplates] = useState<Template[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<string>(templateId ?? "")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !tenantSlug) return
    setSelectedTemplate(templateId ?? "")
  }, [open, tenantSlug, templateId])

  useEffect(() => {
    if (!open || !tenantSlug) return
    async function loadTemplates() {
      const token = await getToken()
      const list = await fetchTemplates(tenantSlug!, token)
      setTemplates(list)
    }
    void loadTemplates()
  }, [open, tenantSlug])

  useEffect(() => {
    if (!open || !tenantSlug || !siteId) return
    setLoading(true)
    setError(null)
    let cancelled = false
    void (async () => {
      const token = await getToken()
      if (cancelled) return
      try {
        const data = await fetchSitePreview(
          tenantSlug,
          token,
          siteId,
          selectedTemplate || undefined
        )
        if (cancelled) return
        setPreview(data)
        if (!data) setError("Preview unavailable")
      } catch {
        if (!cancelled) setError("Failed to load preview")
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [open, tenantSlug, siteId, selectedTemplate])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <ExternalLink className="size-4" />
            Preview: {siteName}
          </SheetTitle>
        </SheetHeader>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium">Template</label>
            <select
              value={selectedTemplate}
              onChange={(e) => setSelectedTemplate(e.target.value)}
              className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            >
              <option value="">Use site template</option>
              {templates.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="size-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : preview ? (
            <PreviewMockup preview={preview} />
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  )
}
