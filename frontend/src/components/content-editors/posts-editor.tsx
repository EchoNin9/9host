/**
 * Updates/Blog editor (Task 2.91).
 * List posts, create/edit/delete. Draft vs Published. Publish flow.
 */
import { useState, useCallback, useEffect, useRef } from "react"
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
import { RichTextEditor } from "@/components/ui/rich-text-editor"
import { getToken } from "@/lib/api"
import {
  fetchContentPosts,
  createContentPost,
  updateContentPost,
  deleteContentPost,
  type ContentPost,
} from "@/lib/api"
import { useTenant } from "@/hooks/use-tenant"

export function PostsEditor({ siteId }: { siteId: string }) {
  const { tenantSlug } = useTenant()
  const [posts, setPosts] = useState<ContentPost[]>([])
  const [loading, setLoading] = useState(true)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editing, setEditing] = useState<ContentPost | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ContentPost | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!tenantSlug || !siteId) return
    setLoading(true)
    try {
      const token = await getToken()
      const list = await fetchContentPosts(tenantSlug, token, siteId)
      setPosts(list)
    } catch {
      setPosts([])
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

  const handleEdit = (post: ContentPost) => {
    setEditing(post)
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
    const ok = await deleteContentPost(tenantSlug, token, siteId, deleteTarget.id)
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
            <CardTitle>Posts</CardTitle>
            <CardDescription>Blog posts and updates. Draft vs Published.</CardDescription>
          </div>
          <Button size="sm" onClick={handleCreate}>
            <Plus className="mr-2 size-4" />
            Add post
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : posts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No posts yet. Add your first post.</p>
          ) : (
            <ul className="space-y-2">
              {posts.map((post) => (
                <li
                  key={post.id}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <div>
                    <p className="font-medium">{post.title || "(Untitled)"}</p>
                    <p className="text-xs text-muted-foreground">
                      /{post.slug} · {post.status}
                      {post.published_at && ` · ${new Date(post.published_at).toLocaleDateString()}`}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleEdit(post)}
                      aria-label="Edit"
                    >
                      <Pencil className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteTarget(post)}
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

      <PostFormSheet
        open={sheetOpen}
        onOpenChange={(open) => !open && handleClose()}
        siteId={siteId}
        post={editing}
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
            <AlertDialogTitle>Delete post?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete &quot;{deleteTarget?.title || deleteTarget?.slug}&quot;.
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

function PostFormSheet({
  open,
  onOpenChange,
  siteId,
  post,
  onSaved,
  saving,
  setSaving,
  error,
  setError,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  siteId: string
  post: ContentPost | null
  onSaved: () => void
  saving: boolean
  setSaving: (v: boolean) => void
  error: string | null
  setError: (v: string | null) => void
}) {
  const { tenantSlug } = useTenant()
  const [slug, setSlug] = useState("")
  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const [status, setStatus] = useState<"DRAFT" | "PUBLISHED">("DRAFT")
  const initialValues = useRef({ slug: "", title: "", body: "", status: "DRAFT" })
  const isDirty = slug !== initialValues.current.slug ||
    title !== initialValues.current.title ||
    body !== initialValues.current.body ||
    status !== initialValues.current.status

  useEffect(() => {
    if (open) {
      const s = post?.slug ?? ""
      const t = post?.title ?? ""
      const b = post?.body ?? ""
      const st = (post?.status?.toUpperCase() as "DRAFT" | "PUBLISHED") || "DRAFT"
      setSlug(s)
      setTitle(t)
      setBody(b)
      setStatus(st)
      initialValues.current = { slug: s, title: t, body: b, status: st }
      setError(null)
    }
  }, [open, post, setError])

  useEffect(() => {
    if (!isDirty) return
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault() }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [isDirty])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!tenantSlug) return
    setSaving(true)
    setError(null)
    try {
      const token = await getToken()
      if (post) {
        const updated = await updateContentPost(
          tenantSlug,
          token,
          siteId,
          post.id,
          { slug: slug.trim() || undefined, title: title.trim(), body, status }
        )
        if (updated) onSaved()
        else setError("Failed to update post")
      } else {
        const created = await createContentPost(
          tenantSlug,
          token,
          siteId,
          { slug: slug.trim() || undefined, title: title.trim(), body, status }
        )
        if (created) onSaved()
        else setError("Failed to create post")
      }
    } catch {
      setError("Request failed")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={(v) => {
      if (!v && isDirty && !confirm("You have unsaved changes. Discard?")) return
      onOpenChange(v)
    }}>
      <SheetContent aria-describedby={undefined} className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {post ? "Edit post" : "Add post"}
            {isDirty && (
              <span className="inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
                Unsaved
              </span>
            )}
          </SheetTitle>
        </SheetHeader>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <Label htmlFor="slug">Slug</Label>
            <Input
              id="slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
              placeholder="my-post"
            />
          </div>
          <div>
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Post title"
            />
          </div>
          <div>
            <Label>Body</Label>
            <RichTextEditor
              value={body}
              onChange={setBody}
              placeholder="Post content…"
              siteId={siteId}
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
              {saving ? "Saving…" : post ? "Save" : "Create"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}
