/** Site data the editor fields pick from (pages, posts, media with display URLs). */
import { createContext } from "react"
import type { MediaRow, PageRow, PostRow } from "@/editor/block-env"
import type { LinkTarget } from "@/components/ui/rich-text-editor"

export interface EditorData {
  siteId: string
  pages: PageRow[]
  posts: PostRow[]
  media: MediaRow[]
  /** Rich-text "Link to page" targets. */
  linkTargets?: LinkTarget[]
}

export const EditorDataContext = createContext<EditorData>({ siteId: "", pages: [], posts: [], media: [] })
