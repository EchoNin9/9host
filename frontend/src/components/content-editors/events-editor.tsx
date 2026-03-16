/**
 * Events/Shows editor (Task 2.92).
 * List events, CRUD, date/venue.
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
import { getToken } from "@/lib/api"
import {
  fetchContentEvents,
  createContentEvent,
  updateContentEvent,
  deleteContentEvent,
  type ContentEvent,
} from "@/lib/api"
import { useTenant } from "@/hooks/use-tenant"

export function EventsEditor({ siteId }: { siteId: string }) {
  const { tenantSlug } = useTenant()
  const [events, setEvents] = useState<ContentEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [editing, setEditing] = useState<ContentEvent | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ContentEvent | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!tenantSlug || !siteId) return
    setLoading(true)
    try {
      const token = await getToken()
      const list = await fetchContentEvents(tenantSlug, token, siteId)
      setEvents(list)
    } catch {
      setEvents([])
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

  const handleEdit = (event: ContentEvent) => {
    setEditing(event)
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
    const ok = await deleteContentEvent(tenantSlug, token, siteId, deleteTarget.id)
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
            <CardTitle>Events</CardTitle>
            <CardDescription>Events, shows, tour dates. Date and venue.</CardDescription>
          </div>
          <Button size="sm" onClick={handleCreate}>
            <Plus className="mr-2 size-4" />
            Add event
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : events.length === 0 ? (
            <p className="text-sm text-muted-foreground">No events yet. Add your first event.</p>
          ) : (
            <ul className="space-y-2">
              {events.map((ev) => (
                <li
                  key={ev.id}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <div>
                    <p className="font-medium">{ev.title || "(Untitled)"}</p>
                    <p className="text-xs text-muted-foreground">
                      {ev.event_date ? new Date(ev.event_date).toLocaleDateString() : "—"}
                      {ev.venue && ` · ${ev.venue}`}
                      {ev.location && ` · ${ev.location}`}
                      {` · ${ev.status}`}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleEdit(ev)}
                      aria-label="Edit"
                    >
                      <Pencil className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteTarget(ev)}
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

      <EventFormSheet
        open={sheetOpen}
        onOpenChange={(open) => !open && handleClose()}
        siteId={siteId}
        event={editing}
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
            <AlertDialogTitle>Delete event?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete &quot;{deleteTarget?.title}&quot;.
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

function EventFormSheet({
  open,
  onOpenChange,
  siteId,
  event,
  onSaved,
  saving,
  setSaving,
  error,
  setError,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  siteId: string
  event: ContentEvent | null
  onSaved: () => void
  saving: boolean
  setSaving: (v: boolean) => void
  error: string | null
  setError: (v: string | null) => void
}) {
  const { tenantSlug } = useTenant()
  const [title, setTitle] = useState("")
  const [eventDate, setEventDate] = useState("")
  const [venue, setVenue] = useState("")
  const [location, setLocation] = useState("")
  const [status, setStatus] = useState<"DRAFT" | "PUBLISHED">("DRAFT")

  useEffect(() => {
    if (open) {
      setTitle(event?.title ?? "")
      setEventDate(event?.event_date ? event.event_date.slice(0, 10) : "")
      setVenue(event?.venue ?? "")
      setLocation(event?.location ?? "")
      setStatus((event?.status?.toUpperCase() as "DRAFT" | "PUBLISHED") || "DRAFT")
      setError(null)
    }
  }, [open, event, setError])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!tenantSlug) return
    setSaving(true)
    setError(null)
    try {
      const token = await getToken()
      const payload = {
        title: title.trim(),
        event_date: eventDate || undefined,
        venue: venue.trim() || undefined,
        location: location.trim() || undefined,
        status,
      }
      if (event) {
        const updated = await updateContentEvent(
          tenantSlug,
          token,
          siteId,
          event.id,
          payload
        )
        if (updated) onSaved()
        else setError("Failed to update event")
      } else {
        const created = await createContentEvent(
          tenantSlug,
          token,
          siteId,
          payload
        )
        if (created) onSaved()
        else setError("Failed to create event")
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
          <SheetTitle>{event ? "Edit event" : "Add event"}</SheetTitle>
        </SheetHeader>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Event title"
            />
          </div>
          <div>
            <Label htmlFor="event_date">Date</Label>
            <Input
              id="event_date"
              type="date"
              value={eventDate}
              onChange={(e) => setEventDate(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="venue">Venue</Label>
            <Input
              id="venue"
              value={venue}
              onChange={(e) => setVenue(e.target.value)}
              placeholder="Venue name"
            />
          </div>
          <div>
            <Label htmlFor="location">Location</Label>
            <Input
              id="location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="City, Country"
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
              {saving ? "Saving…" : event ? "Save" : "Create"}
            </Button>
          </SheetFooter>
        </form>
      </SheetContent>
    </Sheet>
  )
}
