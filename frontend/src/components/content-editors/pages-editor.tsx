/**
 * Pages editor — CRUD for static pages (home, about, contact, etc.).
 * Modeled after PostsEditor (Task 2.91).
 */
import { useState, useCallback, useEffect } from "react"
import { Plus, Pencil, Trash2 } from "lucide-react"
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
import { Textarea } from "@/components/ui/textarea"
import { getToken } from "@/lib/api"
import {
  fetchContentPages,
  createContentPage,
  updateContentPage,
  deleteContentPage,
  type ContentPage,
} from "@/lib/api"
import { useTenant } from "@/hooks/use-tenant"

export function PagesEditor({ siteId }: { siteId: string }) {
  const { tenantSlug } = useTenant()
  const [pages, setPages] = useState<ContentPage[]>([])
  const [loading, setLoading] = useState(true)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editing, setEditing] = useState<ContentPage | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ContentPage | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!tenantSlug || !siteId) return
    setLoading(true)
    try {
      const token = await getToken()
      const list = await fetchContentPages(tenantSlug, token, siteId)
      setPages(list)
    } catch {
      setPages([])
    } finally {
      setLoading(false)
    }
  }, [tenantSlug, siteId])

  useEffect(() => {
    void load()
  }, [load])

  const handleCreate = () => {
    setEditing(null)
    setSheetOpen(true)
  }

  const handleEdit = (page: ContentPage) => {
    setEditing(page)
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
    const ok = await deleteContentPage(tenantSlug, token, siteId, deleteTarget.path)
    if (ok) {
      void load()
      setDeleteTarget(null)
    }
  }

  if (!tenantSlug) return null

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <div>
            <CardTitle>Pages</CardTitle>
            <CardDescription>Static pages like About, Contact, Services, etc.</CardDescription>
          </div>
          <Button size="sm" onClick={handleCreate}>
            <Plus className="mr-2 size-4" />
            Add page
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : pages.length === 0 ? (
            <p className="text-sm text-muted-foreground">No pages yet. Add your first page.</p>
          ) : (
            <ul className="space-y-2">
              {pages.map((page) => (
                <li
                  key={page.path}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <div>
                    <p className="font-medium">{page.title || "(Untitled)"}</p>
                    <p className="text-xs text-muted-foreground">
                      /{page.path} · {page.status}
                      {page.published_at && ` · ${new Date(page.published_at).toLocaleDateString()}`}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleEdit(page)}
                      aria-label="Edit"
                    >
                      <Pencil className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteTarget(page)}
                      aria-label="Delete"
                    >
                      <Trash2 className="size-4 text-destructive" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <PageFormSheet
        open={sheetOpen}
        onOpenChange={(open) => !open && handleClose()}
        siteId={siteId}
        page={editing}
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
            <AlertDialogTitle>Delete page?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete &quot;{deleteTarget?.title || deleteTarget?.path}&quot;.
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

function PageFormSheet({
  open,
  onOpenChange,
  siteId,
  page,
  onSaved,
  saving,
  setSaving,
  error,
  setError,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  siteId: string
  page: ContentPage | null
  onSaved: () => void
  saving: boolean
  setSaving: (v: boolean) => void
  error: string | null
  setError: (v: string | null) => void
}) {
  const { tenantSlug } = useTenant()
  const [path, setPath] = useState("")
  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const [status, setStatus] = useState<"DRAFT" | "PUBLISHED">("DRAFT")

  useEffect(() => {
    if (open) {
      setPath(page?.path ?? "")
      setTitle(page?.title ?? "")
      setBody(page?.body ?? "")
      setStatus((page?.status?.toUpperCase() as "DRAFT" | "PUBLISHED") || "DRAFT")
      setError(null)
    }
  }, [open, page, setError])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!tenantSlug) return
    const trimmedPath = path.trim().toLowerCase().replace(/[^a-z0-9-]/g, "")
    if (!trimmedPath) {
      setError("Path is required (e.g. about, contact)")
      return
    }
    setSaving(true)
    setError(null)
    try {
      const token = await getToken()
      if (page) {
        const updated = await updateContentPage(
          tenantSlug,
          token,
          siteId,
          page.path,
          { title: title.trim(), body, status }
        )
        if (updated) onSaved()
        else setError("Failed to update page")
      } else {
        const created = await createContentPage(
          tenantSlug,
          token,
          siteId,
          { path: trimmedPath, title: title.trim(), body, status }
        )
        if (created) onSaved()
        else setError("Failed to create page")
      }
    } catch {
      setError("Request failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent aria-describedby={undefined} className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{page ? "Edit page" : "Add page"}</SheetTitle>
        </SheetHeader>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <Label htmlFor="path">Path</Label>
            <Input
              id="path"
              value={path}
              onChange={(e) => setPath(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
              placeholder="about"
              disabled={!!page}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              URL path for this page (e.g. &quot;about&quot; → /about/)
            </p>
          </div>
          <div>
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="About Us"
            />
          </div>
          <div>
            <Label htmlFor="body">Body</Label>
            <Textarea
              id="body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Page content…"
              rows={10}
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
              {saving ? "Saving…" : page ? "Save" : "Create"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}
