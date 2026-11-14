/**
 * RichTextEditor — TipTap WYSIWYG wrapper (Task 3.2, 4.2, 4.3).
 *
 * Toolbar: bold, italic, underline, headings, link, image, lists, blockquote, code.
 * When siteId is provided: "Insert image" opens MediaPicker (4.2), drag-and-drop uploads (4.3).
 * When linkTargets is provided: "Link" opens an inline panel with a "Link to page" picker that
 * inserts root-relative hrefs (ADR-0003 §3); otherwise it is the plain URL prompt.
 * Outputs HTML string via onChange callback.
 */
import { useEditor, EditorContent } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import Link from "@tiptap/extension-link"
import Image from "@tiptap/extension-image"
import Underline from "@tiptap/extension-underline"
import { useEffect, useCallback, useState } from "react"
import {
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Heading1,
  Heading2,
  Heading3,
  List,
  ListOrdered,
  Quote,
  Code,
  Link as LinkIcon,
  Image as ImageIcon,
  Undo,
  Redo,
  RemoveFormatting,
  Upload,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { NativeSelect } from "@/components/ui/native-select"
import { MediaPicker, uploadFileAndGetUrl } from "@/components/content-editors/media-picker"
import { useTenant } from "@/hooks/use-tenant"
import { useTenantScope } from "@/context/tenant-scope-context"

interface RichTextEditorProps {
  value: string
  onChange: (html: string) => void
  placeholder?: string
  /** When provided, enables media picker + drag-and-drop upload */
  siteId?: string
  /** Site pages for the link dialog's "Link to page" picker (root-relative hrefs, home = "/"). */
  linkTargets?: LinkTarget[]
}

export interface LinkTarget {
  label: string
  href: string
}

/** Root-relative site link (not protocol-relative): opens in the same tab. */
const isInternalHref = (href: string) => href.startsWith("/") && !href.startsWith("//")

export function RichTextEditor({ value, onChange, placeholder, siteId, linkTargets }: RichTextEditorProps) {
  const { tenantSlug } = useTenant()
  const { api } = useTenantScope()
  const [pickerOpen, setPickerOpen] = useState(false)
  const [dropActive, setDropActive] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [linkDraft, setLinkDraft] = useState<string | null>(null)
  const hasTargets = !!linkTargets?.length

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: { rel: "noopener noreferrer", target: "_blank" },
      }),
      Image.configure({
        inline: false,
        allowBase64: false,
      }),
      Underline,
    ],
    content: value,
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML())
    },
    editorProps: {
      attributes: {
        class: "rte-content",
        ...(placeholder ? { "data-placeholder": placeholder } : {}),
      },
      // Drag-and-drop image handling (Task 4.3)
      handleDrop: (view, event) => {
        if (!siteId || !tenantSlug) return false
        const files = event.dataTransfer?.files
        if (!files || files.length === 0) return false
        const imageFile = Array.from(files).find((f) => f.type.startsWith("image/"))
        if (!imageFile) return false
        event.preventDefault()
        void handleDropUpload(imageFile, view.state.selection.from)
        return true
      },
      // Paste image handling (also Task 4.3)
      handlePaste: (view, event) => {
        if (!siteId || !tenantSlug) return false
        const items = event.clipboardData?.items
        if (!items) return false
        const imageItem = Array.from(items).find((item) => item.type.startsWith("image/"))
        if (!imageItem) return false
        const file = imageItem.getAsFile()
        if (!file) return false
        event.preventDefault()
        void handleDropUpload(file, view.state.selection.from)
        return true
      },
    },
  })

  // Sync external value changes (e.g. when editing a different item)
  useEffect(() => {
    if (editor && value !== editor.getHTML()) {
      editor.commands.setContent(value, { emitUpdate: false })
    }
  }, [editor, value])

  const setLink = useCallback(() => {
    if (!editor) return
    const prev = editor.getAttributes("link").href
    if (hasTargets) {
      setLinkDraft(prev || "")
      return
    }
    const url = window.prompt("URL", prev || "https://")
    if (url === null) return
    if (url === "") {
      editor.chain().focus().extendMarkRange("link").unsetLink().run()
    } else {
      editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run()
    }
  }, [editor, hasTargets])

  const applyLink = useCallback(
    (href: string, label?: string) => {
      if (!editor) return
      setLinkDraft(null)
      const attrs = isInternalHref(href) ? { href, target: null } : { href }
      if (href && editor.state.selection.empty && !editor.isActive("link")) {
        // Nothing selected: insert the link with the page name (or the URL) as its text.
        editor.chain().focus().insertContent({ type: "text", text: label || href, marks: [{ type: "link", attrs }] }).run()
        return
      }
      const chain = editor.chain().focus().extendMarkRange("link")
      if (!href) chain.unsetLink().run()
      else chain.setLink(attrs).run()
    },
    [editor]
  )

  const addImage = useCallback(() => {
    if (!editor) return
    if (siteId) {
      // Open media picker (Task 4.2)
      setPickerOpen(true)
    } else {
      // Fallback: URL prompt
      const url = window.prompt("Image URL")
      if (url) {
        editor.chain().focus().setImage({ src: url }).run()
      }
    }
  }, [editor, siteId])

  const handlePickerSelect = useCallback(
    (url: string) => {
      if (editor) {
        editor.chain().focus().setImage({ src: url }).run()
      }
    },
    [editor]
  )

  // Handle drag-and-drop / paste file upload (Task 4.3)
  const handleDropUpload = useCallback(
    async (file: File, _pos: number) => {
      if (!tenantSlug || !siteId || !editor) return
      setUploading(true)
      try {
        const url = await uploadFileAndGetUrl(api, siteId, file)
        if (url) {
          editor.chain().focus().setImage({ src: url }).run()
        }
      } finally {
        setUploading(false)
      }
    },
    [api, siteId, editor]
  )

  // Drag-over visual feedback
  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      if (!siteId) return
      e.preventDefault()
      setDropActive(true)
    },
    [siteId]
  )

  const handleDragLeave = useCallback(() => {
    setDropActive(false)
  }, [])

  const handleDrop = useCallback(() => {
    setDropActive(false)
  }, [])

  if (!editor) return null

  return (
    <div
      className={`rte-wrapper rounded-md border border-input relative ${
        dropActive ? "ring-2 ring-primary/50 border-primary" : ""
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="rte-toolbar flex flex-wrap gap-0.5 border-b border-input bg-muted/50 p-1">
        <ToolbarButton
          active={editor.isActive("bold")}
          onClick={() => editor.chain().focus().toggleBold().run()}
          title="Bold"
        >
          <Bold className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          active={editor.isActive("italic")}
          onClick={() => editor.chain().focus().toggleItalic().run()}
          title="Italic"
        >
          <Italic className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          active={editor.isActive("underline")}
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          title="Underline"
        >
          <UnderlineIcon className="size-4" />
        </ToolbarButton>

        <ToolbarDivider />

        <ToolbarButton
          active={editor.isActive("heading", { level: 1 })}
          onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
          title="Heading 1"
        >
          <Heading1 className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          active={editor.isActive("heading", { level: 2 })}
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          title="Heading 2"
        >
          <Heading2 className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          active={editor.isActive("heading", { level: 3 })}
          onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
          title="Heading 3"
        >
          <Heading3 className="size-4" />
        </ToolbarButton>

        <ToolbarDivider />

        <ToolbarButton
          active={editor.isActive("bulletList")}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          title="Bullet list"
        >
          <List className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          active={editor.isActive("orderedList")}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          title="Ordered list"
        >
          <ListOrdered className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          active={editor.isActive("blockquote")}
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          title="Blockquote"
        >
          <Quote className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          active={editor.isActive("codeBlock")}
          onClick={() => editor.chain().focus().toggleCodeBlock().run()}
          title="Code block"
        >
          <Code className="size-4" />
        </ToolbarButton>

        <ToolbarDivider />

        <ToolbarButton
          active={editor.isActive("link")}
          onClick={setLink}
          title="Link"
        >
          <LinkIcon className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          active={false}
          onClick={addImage}
          title={siteId ? "Insert image from media gallery" : "Insert image URL"}
        >
          <ImageIcon className="size-4" />
        </ToolbarButton>

        <ToolbarDivider />

        <ToolbarButton
          active={false}
          onClick={() => editor.chain().focus().clearNodes().unsetAllMarks().run()}
          title="Clear formatting"
        >
          <RemoveFormatting className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          active={false}
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()}
          title="Undo"
        >
          <Undo className="size-4" />
        </ToolbarButton>
        <ToolbarButton
          active={false}
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          title="Redo"
        >
          <Redo className="size-4" />
        </ToolbarButton>
      </div>

      {linkDraft !== null && (
        <div
          role="group"
          aria-label="Link"
          className="flex flex-wrap items-center gap-2 border-b border-input bg-muted/30 p-2"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault()
              applyLink(linkDraft.trim())
            } else if (e.key === "Escape") setLinkDraft(null)
          }}
        >
          <NativeSelect
            aria-label="Link to page"
            className="w-48"
            value={linkTargets?.some((t) => t.href === linkDraft) ? linkDraft : ""}
            onChange={(e) => {
              const t = linkTargets?.find((x) => x.href === e.target.value)
              if (t) applyLink(t.href, t.label)
            }}
          >
            <option value="">Link to page…</option>
            {linkTargets?.map((t) => (
              <option key={t.href} value={t.href}>
                {t.label} ({t.href})
              </option>
            ))}
          </NativeSelect>
          <Input
            aria-label="URL"
            className="h-9 min-w-40 flex-1"
            placeholder="https://"
            value={linkDraft}
            onChange={(e) => setLinkDraft(e.target.value)}
            autoFocus
          />
          <Button type="button" size="sm" onClick={() => applyLink(linkDraft.trim())}>
            Apply
          </Button>
          {editor.isActive("link") && (
            <Button type="button" size="sm" variant="ghost" onClick={() => applyLink("")}>
              Remove
            </Button>
          )}
          <Button type="button" size="sm" variant="ghost" onClick={() => setLinkDraft(null)}>
            Cancel
          </Button>
        </div>
      )}

      <EditorContent editor={editor} className="rte-editor" />

      {/* Upload indicator overlay */}
      {uploading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded-md bg-background/80">
          <div className="flex items-center gap-2 rounded-md bg-card px-4 py-2 shadow-md">
            <Upload className="size-4 animate-bounce text-primary" />
            <span className="text-sm font-medium">Uploading image…</span>
          </div>
        </div>
      )}

      {/* Drop zone overlay */}
      {dropActive && !uploading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded-md bg-primary/10 border-2 border-dashed border-primary">
          <div className="flex items-center gap-2 rounded-md bg-card px-4 py-2 shadow-md">
            <ImageIcon className="size-4 text-primary" />
            <span className="text-sm font-medium">Drop image to upload</span>
          </div>
        </div>
      )}

      {/* Media picker dialog (Task 4.2) */}
      {siteId && (
        <MediaPicker
          open={pickerOpen}
          onOpenChange={setPickerOpen}
          siteId={siteId}
          onSelect={handlePickerSelect}
        />
      )}

      <style>{`
        .rte-editor .tiptap {
          min-height: 200px;
          padding: 0.75rem;
          outline: none;
          font-size: 0.875rem;
          line-height: 1.625;
        }
        .rte-editor .tiptap p { margin-bottom: 0.5rem; }
        .rte-editor .tiptap h1 { font-size: 1.5rem; font-weight: 700; margin: 1rem 0 0.5rem; }
        .rte-editor .tiptap h2 { font-size: 1.25rem; font-weight: 600; margin: 0.75rem 0 0.5rem; }
        .rte-editor .tiptap h3 { font-size: 1.125rem; font-weight: 600; margin: 0.5rem 0 0.25rem; }
        .rte-editor .tiptap ul,
        .rte-editor .tiptap ol { padding-left: 1.5rem; margin-bottom: 0.5rem; }
        .rte-editor .tiptap ul { list-style: disc; }
        .rte-editor .tiptap ol { list-style: decimal; }
        .rte-editor .tiptap blockquote {
          border-left: 3px solid hsl(var(--border));
          padding-left: 1rem;
          margin: 0.5rem 0;
          color: hsl(var(--muted-foreground));
        }
        .rte-editor .tiptap pre {
          background: hsl(var(--muted));
          border-radius: 0.375rem;
          padding: 0.75rem;
          font-family: monospace;
          font-size: 0.8125rem;
          overflow-x: auto;
          margin-bottom: 0.5rem;
        }
        .rte-editor .tiptap code {
          background: hsl(var(--muted));
          border-radius: 0.25rem;
          padding: 0.125rem 0.25rem;
          font-size: 0.8125rem;
        }
        .rte-editor .tiptap a { color: hsl(var(--primary)); text-decoration: underline; }
        .rte-editor .tiptap img {
          max-width: 100%;
          height: auto;
          border-radius: 0.375rem;
          margin: 0.5rem 0;
        }
        .rte-editor .tiptap p.is-editor-empty:first-child::before {
          content: attr(data-placeholder);
          float: left;
          color: hsl(var(--muted-foreground));
          pointer-events: none;
          height: 0;
        }
      `}</style>
    </div>
  )
}

function ToolbarButton({
  active,
  onClick,
  disabled,
  title,
  children,
}: {
  active: boolean
  onClick: () => void
  disabled?: boolean
  title: string
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`inline-flex size-7 items-center justify-center rounded-sm transition-colors ${
        active
          ? "bg-accent text-accent-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      } ${disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
    >
      {children}
    </button>
  )
}

function ToolbarDivider() {
  return <div className="mx-0.5 h-6 w-px self-center bg-border" />
}
