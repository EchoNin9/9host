/** Site data the editor fields pick from (pages, posts, media with display URLs). */
import { createContext } from "react"
import type { MediaRow, PageRow, PostRow } from "@/editor/block-env"

export interface EditorData {
  siteId: string
  pages: PageRow[]
  posts: PostRow[]
  media: MediaRow[]
}

export const EditorDataContext = createContext<EditorData>({ siteId: "", pages: [], posts: [], media: [] })
