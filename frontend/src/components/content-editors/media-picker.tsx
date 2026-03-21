/**
 * Media Picker dialog (Task 4.1).
 *
 * Browse existing uploaded media for a site and select one.
 * Returns the presigned display URL and s3_key of the selected image.
 */
import { useState, useCallback, useEffect, useRef } from "react"
import { ImageIcon, Plus, Check, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { getToken } from "@/lib/api"
import {
  fetchContentMedia,
  fetchMediaPresignedUrl,
  fetchUploadUrl,
  createContentMedia,
  type ContentMedia,
} from "@/lib/api"
import { useTenant } from "@/hooks/use-tenant"

interface MediaPickerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  siteId: string
  onSelect: (url: string) => void
}

interface MediaWithUrl extends ContentMedia {
  displayUrl?: string
}

export function MediaPicker({ open, onOpenChange, siteId, onSelect }: MediaPickerProps) {
  const { tenantSlug } = useTenant()
  const [media, setMedia] = useState<MediaWithUrl[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    if (!tenantSlug || !siteId) return
    setLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const list = await fetchContentMedia(tenantSlug, token, siteId)
      // Fetch presigned URLs for all media items
      const withUrls = await Promise.all(
        list.map(async (m) => {
          const url = await fetchMediaPresignedUrl(tenantSlug, token, siteId, m.id)
          return { ...m, displayUrl: url ?? undefined }
        })
      )
      setMedia(withUrls)
    } catch {
      setMedia([])
      setError("Failed to load media")
    } finally {
      setLoading(false)
    }
  }, [tenantSlug, siteId])

  useEffect(() => {
    if (open) {
      setSelected(null)
      void load()
    }
  }, [open, load])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !tenantSlug) return
    e.target.value = ""
    setUploading(true)
    setError(null)
    try {
      const token = await getToken()
      const uploadResp = await fetchUploadUrl(tenantSlug, token, siteId, {
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
      const uploadRes = await fetch(uploadResp.url, {
        method: "POST",
        body: formData,
      })
      if (!uploadRes.ok) {
        setError("Upload failed")
        return
      }
      await createContentMedia(tenantSlug, token, siteId, {
        s3_key: uploadResp.key,
        caption: "",
        status: "DRAFT",
      })
      await load()
    } catch {
      setError("Upload failed")
    } finally {
      setUploading(false)
    }
  }

  const handleInsert = () => {
    const item = media.find((m) => m.id === selected)
    if (item?.displayUrl) {
      onSelect(item.displayUrl)
      onOpenChange(false)
    }
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <AlertDialogHeader>
          <AlertDialogTitle>Insert Image</AlertDialogTitle>
          <AlertDialogDescription>
            Select an image from your media gallery or upload a new one.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="flex-1 overflow-y-auto min-h-0">
          {error && <p className="mb-2 text-sm text-destructive">{error}</p>}

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          ) : media.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <ImageIcon className="mb-3 size-12 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                No images uploaded yet. Upload one to get started.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
              {media.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setSelected(m.id)}
                  className={`relative aspect-square overflow-hidden rounded-md border-2 transition-all ${
                    selected === m.id
                      ? "border-primary ring-2 ring-primary/30"
                      : "border-transparent hover:border-muted-foreground/30"
                  }`}
                >
                  {m.displayUrl ? (
                    <img
                      src={m.displayUrl}
                      alt={m.caption || ""}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center bg-muted">
                      <ImageIcon className="size-8 text-muted-foreground" />
                    </div>
                  )}
                  {selected === m.id && (
                    <div className="absolute inset-0 flex items-center justify-center bg-primary/20">
                      <div className="rounded-full bg-primary p-1">
                        <Check className="size-4 text-primary-foreground" />
                      </div>
                    </div>
                  )}
                  {m.caption && (
                    <div className="absolute bottom-0 left-0 right-0 truncate bg-black/60 px-1.5 py-0.5 text-[10px] text-white">
                      {m.caption}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <AlertDialogFooter className="flex-row items-center justify-between sm:justify-between">
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleUpload}
              disabled={uploading}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              <Plus className="mr-1.5 size-3.5" />
              {uploading ? "Uploading…" : "Upload new"}
            </Button>
          </div>
          <div className="flex gap-2">
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleInsert} disabled={!selected}>
              Insert
            </AlertDialogAction>
          </div>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

/**
 * Upload a file and return the presigned display URL.
 * Used by drag-and-drop in the RichTextEditor (Task 4.3).
 */
export async function uploadFileAndGetUrl(
  tenantSlug: string,
  siteId: string,
  file: File
): Promise<string | null> {
  try {
    const token = await getToken()
    const uploadResp = await fetchUploadUrl(tenantSlug, token, siteId, {
      content_length: file.size,
      filename: file.name,
    })
    if (!uploadResp) return null

    const formData = new FormData()
    Object.entries(uploadResp.fields).forEach(([k, v]) => formData.append(k, v))
    formData.append("file", file)
    const uploadRes = await fetch(uploadResp.url, {
      method: "POST",
      body: formData,
    })
    if (!uploadRes.ok) return null

    const created = await createContentMedia(tenantSlug, token, siteId, {
      s3_key: uploadResp.key,
      caption: "",
      status: "DRAFT",
    })
    if (!created) return null

    const url = await fetchMediaPresignedUrl(tenantSlug, token, siteId, created.id)
    return url
  } catch {
    return null
  }
}
