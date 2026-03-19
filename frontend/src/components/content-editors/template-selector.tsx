/**
 * Template selector for the site content editor.
 * Allows changing the site's template from available platform templates.
 */
import { useState, useEffect, useCallback } from "react"
import { Check } from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { getToken, fetchTemplates, updateSite, type Template, type Site } from "@/lib/api"
import { useTenant } from "@/hooks/use-tenant"

export function TemplateSelector({ site, onSaved }: { site: Site; onSaved?: () => void }) {
  const { tenantSlug } = useTenant()
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!tenantSlug) return
    setLoading(true)
    try {
      const token = await getToken()
      const list = await fetchTemplates(tenantSlug, token)
      setTemplates(list)
    } catch {
      setTemplates([])
    } finally {
      setLoading(false)
    }
  }, [tenantSlug])

  useEffect(() => {
    void load()
  }, [load])

  const handleSelect = async (templateSlug: string) => {
    if (!tenantSlug || saving) return
    setSaving(true)
    setError(null)
    setSuccessMsg(null)
    try {
      const token = await getToken()
      const updated = await updateSite(tenantSlug, token, site.id, { template_id: templateSlug })
      if (updated) {
        setSuccessMsg(`Template changed to "${templateSlug}". Re-publish to apply.`)
        onSaved?.()
      } else {
        setError("Failed to update template")
      }
    } catch {
      setError("Request failed")
    } finally {
      setSaving(false)
    }
  }

  if (!tenantSlug) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Template</CardTitle>
        <CardDescription>
          Choose a template for your site. Current:{" "}
          <strong>{site.template_id || "none"}</strong>
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading templates…</p>
        ) : templates.length === 0 ? (
          <p className="text-sm text-muted-foreground">No templates available.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {templates.map((t) => {
              const isActive = site.template_id === t.slug
              return (
                <button
                  key={t.slug}
                  type="button"
                  disabled={saving || isActive}
                  onClick={() => handleSelect(t.slug)}
                  className={`relative rounded-lg border p-4 text-left transition-colors ${
                    isActive
                      ? "border-primary bg-primary/5 ring-2 ring-primary"
                      : "border-border hover:border-primary/50 hover:bg-muted/50"
                  } ${saving ? "opacity-50" : ""}`}
                >
                  {isActive && (
                    <div className="absolute right-2 top-2 rounded-full bg-primary p-1">
                      <Check className="size-3 text-primary-foreground" />
                    </div>
                  )}
                  <p className="font-medium">
                    {t.name}
                    {t.is_custom && (
                      <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                        Custom
                      </span>
                    )}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">{t.description}</p>
                  {t.tier_required && t.tier_required !== "FREE" && (
                    <p className="mt-1 text-xs font-medium text-amber-600">{t.tier_required}+</p>
                  )}
                </button>
              )
            })}
          </div>
        )}
        {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
        {successMsg && (
          <p className="mt-3 text-sm text-green-600 dark:text-green-400">{successMsg}</p>
        )}
      </CardContent>
    </Card>
  )
}
