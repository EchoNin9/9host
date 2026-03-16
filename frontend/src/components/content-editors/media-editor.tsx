/**
 * Media gallery editor (Task 2.93).
 * Upload via pre-signed POST, list, caption, reorder.
 */
import { useState, useCallback, useEffect, useRef } from "react"
import { Plus, Pencil, Trash2, ChevronUp, ChevronDown, ImageIcon } from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/ui/sheet"
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
import { Label } from "@/components/ui/label"
import { getToken } from "@/lib/api"
import {
  fetchContentMedia,
  createContentMedia,
  updateContentMedia,
  deleteContentMedia,
  fetchUploadUrl,
  fetchMediaPresignedUrl,
  type ContentMedia,
} from "@/lib/api"
import { useTenant } from "@/hooks/use-tenant"

export function MediaEditor({ siteId }: { siteId: string }) {
  const { tenantSlug } = useTenant()
  const [media, setMedia] = useState<ContentMedia[]>([])
  const [loading, setLoading] = useState(true)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editing, setEditing] = useState<ContentMedia | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ContentMedia | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    if (!tenantSlug || !siteId) return
    setLoading(true)
    try {
      const token = await getToken()
      const list = await fetchContentMedia(tenantSlug, token, siteId)
      setMedia(list)
    } catch {
      setMedia([])
    } finally {
      setLoading(false)
    }
  }, [tenantSlug, siteId])

  useEffect(() => {
    void load()
  }, [load])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !tenantSlug) return
    e.target.value = ""
    setSaving(true)
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
      const created = await createContentMedia(tenantSlug, token, siteId, {
        s3_key: uploadResp.key,
        caption: "",
        status: "DRAFT",
      })
      if (created) void load()
      else setError("Failed to create media record")
    } catch {
      setError("Upload failed")
    } finally {
      setSaving(false)
    }
  }

  const handleEdit = (m: ContentMedia) => {
    setEditing(m)
    setSheetOpen(true)
  }

  const handleClose = () => {
    setSheetOpen(false)
    setEditing(null)
    setError(null)
  }

  const handleDelete = async () => {
    if (!deleteTarget || !tenantSlug) return
    const token = await getToken()
    const ok = await deleteContentMedia(tenantSlug, token, siteId, deleteTarget.id)
    if (ok) {
      void load()
      setDeleteTarget(null)
    }
  }

  const handleReorder = async (m: ContentMedia, direction: "up" | "down") => {
    if (!tenantSlug) return
    const sorted = [...media].sort((a, b) => (a.sort_order ?? 999) - (b.sort_order ?? 999))
    const idx = sorted.findIndex((x) => x.id === m.id)
    if (idx < 0) return
    const swapIdx = direction === "up" ? idx - 1 : idx + 1
    if (swapIdx < 0 || swapIdx >= sorted.length) return
    const [a, b] = [sorted[idx], sorted[swapIdx]]
    const token = await getToken()
    await Promise.all([
      updateContentMedia(tenantSlug, token, siteId, a.id, { sort_order: swapIdx }),
      updateContentMedia(tenantSlug, token, siteId, b.id, { sort_order: idx }),
    ])
    void load()
  }

  if (!tenantSlug) return null

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <div>
            <CardTitle>Media</CardTitle>
            <CardDescription>Image gallery. Upload, caption, reorder.</CardDescription>
          </div>
          <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleUpload}
              disabled={saving}
            />
            <Button
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={saving}
            >
              <Plus className="mr-2 size-4" />
              {saving ? "Uploading…" : "Upload"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {error && <p className="mb-2 text-sm text-destructive">{error}</p>}
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : media.length === 0 ? (
            <p className="text-sm text-muted-foreground">No media yet. Upload an image.</p>
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[...media]
                .sort((a, b) => (a.sort_order ?? 999) - (b.sort_order ?? 999))
                .map((m, idx) => (
                  <MediaCard
                    key={m.id}
                    media={m}
                    tenantSlug={tenantSlug}
                    siteId={siteId}
                    onEdit={() => handleEdit(m)}
                    onDelete={() => setDeleteTarget(m)}
                    onReorderUp={idx > 0 ? () => handleReorder(m, "up") : undefined}
                    onReorderDown={idx < media.length - 1 ? () => handleReorder(m, "down") : undefined}
                  />
                ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <MediaCaptionSheet
        open={sheetOpen}
        onOpenChange={(open) => !open && handleClose()}
        siteId={siteId}
        media={editing}
        onSaved={() => {
          void load()
          handleClose()
        }}
        saving={saving}
        setSaving={setSaving}
        error={error}
        setError={setError}
      />

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent aria-describedby={undefined}>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete media?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this item and remove the file from storage.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

function MediaCard({
  media,
  tenantSlug,
  siteId,
  onEdit,
  onDelete,
  onReorderUp,
  onReorderDown,
}: {
  media: ContentMedia
  tenantSlug: string
  siteId: string
  onEdit: () => void
  onDelete: () => void
  onReorderUp?: () => void
  onReorderDown?: () => void
}) {
  const [imgUrl, setImgUrl] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    getToken().then((token) => {
      if (cancelled) return
      fetchMediaPresignedUrl(tenantSlug, token, siteId, media.id).then((url) => {
        if (!cancelled && url) setImgUrl(url)
      })
    })
    return () => {
      cancelled = true
    }
  }, [tenantSlug, siteId, media.id])

  return (
    <li className="flex flex-col rounded-md border overflow-hidden">
      <div className="aspect-video bg-muted flex items-center justify-center">
        {imgUrl ? (
          <img src={imgUrl} alt={media.caption || ""} className="object-cover w-full h-full" />
        ) : (
          <ImageIcon className="size-12 text-muted-foreground" />
        )}
      </div>
      <div className="p-2 flex items-center justify-between gap-2">
        <p className="text-sm truncate flex-1">{media.caption || "(no caption)"}</p>
        <div className="flex gap-1 shrink-0">
          {onReorderUp && (
            <Button variant="ghost" size="icon" onClick={onReorderUp} aria-label="Move up">
              <ChevronUp className="size-4" />
            </Button>
          )}
          {onReorderDown && (
            <Button variant="ghost" size="icon" onClick={onReorderDown} aria-label="Move down">
              <ChevronDown className="size-4" />
            </Button>
          )}
          <Button variant="ghost" size="icon" onClick={onEdit} aria-label="Edit">
            <Pencil className="size-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={onDelete} aria-label="Delete">
            <Trash2 className="size-4 text-destructive" />
          </Button>
        </div>
      </div>
    </li>
  )
}

function MediaCaptionSheet({
  open,
  onOpenChange,
  siteId,
  media,
  onSaved,
  saving,
  setSaving,
  error,
  setError,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  siteId: string
  media: ContentMedia | null
  onSaved: () => void
  saving: boolean
  setSaving: (v: boolean) => void
  error: string | null
  setError: (v: string | null) => void
}) {
  const { tenantSlug } = useTenant()
  const [caption, setCaption] = useState("")
  const [status, setStatus] = useState<"DRAFT" | "PUBLISHED">("DRAFT")

  useEffect(() => {
    if (open && media) {
      setCaption(media.caption ?? "")
      setStatus((media.status?.toUpperCase() as "DRAFT" | "PUBLISHED") || "DRAFT")
      setError(null)
    }
  }, [open, media, setError])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!tenantSlug || !media) return
    setSaving(true)
    setError(null)
    try {
      const token = await getToken()
      const updated = await updateContentMedia(
        tenantSlug,
        token,
        siteId,
        media.id,
        { caption, status }
      )
      if (updated) onSaved()
      else setError("Failed to update")
    } catch {
      setError("Request failed")
    } finally {
      setSaving(false)
    }
  }

  if (!media) return null

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent aria-describedby={undefined}>
        <SheetHeader>
          <SheetTitle>Edit media</SheetTitle>
        </SheetHeader>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <Label htmlFor="caption">Caption</Label>
            <Input
              id="caption"
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              placeholder="Image caption"
            />
          </div>
          <div>
            <Label>Status</Label>
            <div className="flex gap-4 pt-2">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  checked={status === "DRAFT"}
                  onChange={() => setStatus("DRAFT")}
                />
                Draft
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  checked={status === "PUBLISHED"}
                  onChange={() => setStatus("PUBLISHED")}
                />
                Published
              </label>
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <SheetFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}
