import { useState } from "react"
import { LayoutTemplate } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { Notice } from "@/components/page"
import { useTenantScope } from "@/context/tenant-scope-context"
import { setSiteEditor } from "@/lib/api"

/** "Switch this site to the block editor" with confirmation (ADR-0003 §4, site.editor). */
export function SwitchToBlocksButton({
  siteId,
  onSwitched,
  size,
}: {
  siteId: string
  onSwitched: () => void
  size?: "sm" | "default"
}) {
  const { api } = useTenantScope()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  return (
    <>
      <Button size={size} variant="outline" onClick={() => setOpen(true)}>
        <LayoutTemplate className="size-4" />
        Switch to block editor
      </Button>
      {error && <Notice tone="danger">{error}</Notice>}
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Switch this site to the block editor?"
        description="Pages are edited visually with blocks (hero, columns, images, buttons). Existing page text is kept as one text block you can split up."
        destructive={false}
        confirmLabel="Switch to block editor"
        pendingLabel="Switching…"
        onConfirm={async () => {
          setError(null)
          const r = await setSiteEditor(api, siteId, "blocks")
          if (!r.ok) {
            setError(r.error)
            return true
          }
          onSwitched()
        }}
      />
    </>
  )
}
