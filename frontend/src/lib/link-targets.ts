/** Rich-text "Link to page" targets: root-relative hrefs the compiler serves (ADR-0003 §3). */
import type { LinkTarget } from "@/components/ui/rich-text-editor"

export const HOME_PAGE_PATH = "_home"

export function siteLinkTargets(
  pages: { path: string; title?: string }[],
  has: { blog?: boolean; events?: boolean; gallery?: boolean } = {}
): LinkTarget[] {
  const out: LinkTarget[] = [{ label: "Home", href: "/" }]
  for (const p of pages) {
    const path = p.path.trim().replace(/^\/+|\/+$/g, "")
    if (path && path !== HOME_PAGE_PATH) out.push({ label: p.title || path, href: `/${path}/` })
  }
  if (has.blog) out.push({ label: "Blog", href: "/blog/" })
  if (has.events) out.push({ label: "Events", href: "/events/" })
  if (has.gallery) out.push({ label: "Gallery", href: "/gallery/" })
  return out
}
