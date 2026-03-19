/**
 * Branding editor (Task 2.94).
 * Logo, colors, fonts. Store in site settings.
 */
import { useState, useRef, useEffect } from "react"
import { Upload, ImageIcon } from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { getToken } from "@/lib/api"
import {
  fetchUploadUrl,
  updateSite,
  type Site,
  type SiteBranding,
} from "@/lib/api"
import { useTenant } from "@/hooks/use-tenant"

const FONT_OPTIONS = [
  "",
  "Inter",
  "Roboto",
  "Open Sans",
  "Lato",
  "Montserrat",
  "Poppins",
  "Playfair Display",
  "Merriweather",
]

export function BrandingEditor({ site, onSaved }: { site: Site; onSaved?: () => void }) {
  const { tenantSlug } = useTenant()
  const [logoS3Key, setLogoS3Key] = useState(site.branding?.logo_s3_key ?? "")
  const [primaryColor, setPrimaryColor] = useState(site.branding?.primary_color ?? "")
  const [fontFamily, setFontFamily] = useState(site.branding?.font_family ?? "")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setLogoS3Key(site.branding?.logo_s3_key ?? "")
    setPrimaryColor(site.branding?.primary_color ?? "")
    setFontFamily(site.branding?.font_family ?? "")
  }, [site.branding])
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !tenantSlug) return
    e.target.value = ""
    setSaving(true)
    setError(null)
    try {
      const token = await getToken()
      const uploadResp = await fetchUploadUrl(tenantSlug, token, site.id, {
        content_length: file.size,
        filename: file.name,
      })
      if (!uploadResp) {
        setError("Failed to get upload URL")
        return
      }
      const formData = new FormData()
      Object.entries(uploadResp.fields).forEach(([k, v]) => formData.append(k, v))
      formData.append("file", file)
      const uploadRes = await fetch(uploadResp.url, { method: "POST", body: formData })
      if (!uploadRes.ok) {
        setError("Upload failed")
        return
      }
      setLogoS3Key(uploadResp.key)
    } catch {
      setError("Upload failed")
    } finally {
      setSaving(false)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!tenantSlug) return
    setSaving(true)
    setError(null)
    try {
      const token = await getToken()
      const branding: SiteBranding = {}
      if (logoS3Key) branding.logo_s3_key = logoS3Key
      if (primaryColor) branding.primary_color = primaryColor.trim()
      if (fontFamily) branding.font_family = fontFamily.trim()
      const updated = await updateSite(tenantSlug, token, site.id, { branding })
      if (updated) {
        setError(null)
        onSaved?.()
      } else setError("Failed to save")
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
        <CardTitle>Branding</CardTitle>
        <CardDescription>Logo, colors, fonts for your site.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSave} className="space-y-6">
          <div>
            <Label>Logo</Label>
            <div className="mt-2 flex items-center gap-4">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleLogoUpload}
                disabled={saving}
              />
              <div className="flex size-20 items-center justify-center overflow-hidden rounded border bg-muted">
                {logoS3Key ? (
                  <img
                    src={`/media/${logoS3Key}`}
                    alt="Site logo"
                    className="size-full object-contain"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none"
                      ;(e.target as HTMLImageElement).parentElement!.innerHTML =
                        '<span class="text-xs text-muted-foreground">Logo uploaded</span>'
                    }}
                  />
                ) : (
                  <ImageIcon className="size-10 text-muted-foreground" />
                )}
              </div>
              <Button
                type="button"
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                disabled={saving}
              >
                <Upload className="mr-2 size-4" />
                {logoS3Key ? "Replace" : "Upload"}
              </Button>
            </div>
          </div>
          <div>
            <Label htmlFor="primary_color">Primary color</Label>
            <div className="mt-1 flex gap-2">
              <Input
                id="primary_color"
                type="color"
                value={primaryColor || "#0d9488"}
                onChange={(e) => setPrimaryColor(e.target.value)}
                className="h-10 w-14 p-1 cursor-pointer"
              />
              <Input
                value={primaryColor}
                onChange={(e) => setPrimaryColor(e.target.value)}
                placeholder="#0d9488"
                className="flex-1"
              />
            </div>
          </div>
          <div>
            <Label htmlFor="font_family">Font family</Label>
            <select
              id="font_family"
              value={fontFamily}
              onChange={(e) => setFontFamily(e.target.value)}
              className="mt-1 h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
            >
              {FONT_OPTIONS.map((f) => (
                <option key={f || "default"} value={f}>
                  {f || "Default"}
                </option>
              ))}
            </select>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save branding"}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

