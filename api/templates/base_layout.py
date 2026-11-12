"""
Base layout and TemplateRenderer (Task 1.112).

Shared HTML structure, branding injection, and utilities.
Template-specific layouts extend TemplateRenderer.
"""

import html
import re
from abc import ABC, abstractmethod

from html_sanitizer import sanitize_html


def escape_html(s: str) -> str:
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def media_url(s3_key: str, media_base: str) -> str:
    """Build media URL: /media/{tenant}/{site}/{filename}."""
    if not s3_key:
        return ""
    base = (media_base or "/media").rstrip("/")
    return f"{base}/{s3_key}"


def rewrite_body_media_urls(body: str, tenant_slug: str, site_id: str, media_base: str) -> str:
    """Rewrite S3/presigned URLs in body to /media/{tenant}/{site}/{filename}."""
    if not body or not isinstance(body, str):
        return body or ""
    pattern = re.compile(
        r"https?://[^\s\"'<>]*?/" + re.escape(f"{tenant_slug}/{site_id}/") + r"([^\s\"'<>?#]+)",
        re.IGNORECASE,
    )
    base = (media_base or "/media").rstrip("/")

    def repl(m: re.Match) -> str:
        return f"{base}/{tenant_slug}/{site_id}/{m.group(1)}"

    return pattern.sub(repl, body)


_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")
_FONT_RE = re.compile(r"^[A-Za-z0-9 ,'\-]{1,100}$")


def branding_styles(branding: dict) -> str:
    """Generate CSS custom properties from site.branding.

    Values are interpolated into <style>, where HTML escaping does not help, so only strictly
    matching colours (#hex) and font names are emitted; anything else falls back to the template default.
    """
    if not branding or not isinstance(branding, dict):
        return ""

    def ok(key: str, pattern: re.Pattern) -> str | None:
        v = branding.get(key)
        return v if isinstance(v, str) and pattern.match(v) else None

    parts = []
    for key, prop in (("primary_color", "--brand-primary"), ("secondary_color", "--brand-secondary")):
        if (v := ok(key, _COLOR_RE)):
            parts.append(f"  {prop}: {v};")
    if (v := ok("font_family", _FONT_RE)):
        parts.append(f"  --brand-font: {v}, sans-serif;")
    for key, prop in (("background_color", "--brand-bg"), ("text_color", "--brand-text")):
        if (v := ok(key, _COLOR_RE)):
            parts.append(f"  {prop}: {v};")
    if not parts:
        return ""
    return "<style>\n:root {\n" + "\n".join(parts) + "\n}\n</style>\n  "


def nav_links(pages: list, has_posts: bool, has_events: bool, has_media: bool = False, base_path: str = "") -> str:
    """Build nav links from pages + blog + events + gallery.

    base_path: URL prefix for internal links — "" (live: root-relative /, /blog/, ...)
    or "/preview" (draft).
    """
    base = base_path.rstrip("/")
    links = []
    for p in pages:
        path = (p.get("path") or "").strip().strip("/")
        if path:
            links.append(f'<li><a href="{base}/{escape_html(path)}/">{escape_html(p.get("title") or path)}</a></li>')
    if has_posts:
        links.append(f'<li><a href="{base}/blog/">Blog</a></li>')
    if has_events:
        links.append(f'<li><a href="{base}/events/">Events</a></li>')
    if has_media:
        links.append(f'<li><a href="{base}/gallery/">Gallery</a></li>')
    return "\n      ".join(links) if links else ""


def rich_text_content_css() -> str:
    """Shared CSS for rich text (TipTap) HTML output in .content blocks (Task 3.5)."""
    return """
/* Rich text content styles (Task 3.5) */
.content h1 { font-size: 1.75rem; font-weight: 700; margin: 1.5rem 0 0.75rem; }
.content h2 { font-size: 1.4rem; font-weight: 600; margin: 1.25rem 0 0.5rem; }
.content h3 { font-size: 1.15rem; font-weight: 600; margin: 1rem 0 0.5rem; }
.content ul { list-style: disc; margin-left: 1.5rem; margin-bottom: 1rem; }
.content ol { list-style: decimal; margin-left: 1.5rem; margin-bottom: 1rem; }
.content li { margin-bottom: 0.25rem; }
.content blockquote {
  border-left: 3px solid var(--brand-primary, var(--template-primary, #6b7280));
  padding-left: 1rem;
  margin: 1rem 0;
  color: var(--template-muted, #6b7280);
  font-style: italic;
}
.content pre {
  background: #1e1e2e;
  color: #cdd6f4;
  border-radius: 6px;
  padding: 1rem;
  overflow-x: auto;
  margin-bottom: 1rem;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  line-height: 1.5;
}
.content code {
  background: rgba(0,0,0,0.06);
  border-radius: 3px;
  padding: 0.125rem 0.375rem;
  font-family: 'Courier New', monospace;
  font-size: 0.875em;
}
.content pre code { background: none; padding: 0; border-radius: 0; }
.content a { color: var(--brand-primary, var(--template-primary, #2563eb)); text-decoration: underline; }
.content a:hover { opacity: 0.8; }
.content u { text-decoration: underline; }
"""


def _document(head: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
</head>
<body>
{body}
</body>
</html>"""


def _plain_text(html_fragment: str) -> str:
    """Tags stripped, entities decoded, whitespace collapsed (for meta descriptions)."""
    text = re.sub(r"<[^>]*>", " ", html_fragment or "")
    return " ".join(html.unescape(text).split())


def _list_or(items: str, empty: str) -> str:
    """Return items, or an empty-state line (kept out of f-string expressions: Python 3.11)."""
    return items or empty


class TemplateRenderer(ABC):
    """
    Base class for template-specific HTML/CSS rendering.
    Each template implements its own layout and theme (render_css).

    base_path is the URL prefix for every internal link: "" in live mode (root-relative
    /, /blog/, /posts/{slug}/, /events/, /gallery/) and "/preview" in draft mode.
    Rich-text bodies pass through sanitize_html(); all plain-text fields are escaped.
    Rendering is pure: the footer year comes from ``footer_year`` (set by the caller),
    never from the clock.
    """

    footer_year: str = ""

    def html_head(
        self,
        title: str,
        site_name: str,
        branding: dict,
        media_base: str,
        base_path: str = "",
        meta_description: str = "",
        meta_image: str = "",
    ) -> str:
        """Generate <head> with meta, title, stylesheet link, branding overrides (Task 1.128 SEO)."""
        styles = branding_styles(branding)
        css_link = f'  <link rel="stylesheet" href="{base_path.rstrip("/")}/style.css">'
        page_title = f"{escape_html(title or site_name)} — {escape_html(site_name)}"
        meta_parts = []
        if meta_description:
            meta_parts.append(f'  <meta name="description" content="{escape_html(meta_description[:160])}">')
        if meta_image:
            meta_parts.append(f'  <meta property="og:image" content="{escape_html(meta_image)}">')
        meta_parts.append(f'  <meta property="og:title" content="{page_title}">')
        meta_block = "\n".join(meta_parts) + "\n"
        return f"""  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{page_title}</title>
{meta_block}{css_link}
{styles}"""

    def html_header(
        self,
        site_name: str,
        branding: dict,
        media_base: str,
        nav_links_html: str,
    ) -> str:
        """Generate header with logo and nav."""
        logo_html = ""
        if branding and isinstance(branding, dict) and branding.get("logo_s3_key"):
            logo_url = media_url(branding["logo_s3_key"], media_base)
            logo_html = f'<img src="{escape_html(logo_url)}" alt="" class="site-logo"> '
        return f"""<div class="site-wrapper">
  <header class="site-header">
    {logo_html}<h1 class="site-title">{escape_html(site_name)}</h1>
    <nav class="site-nav"><ul>{nav_links_html}</ul></nav>
  </header>"""

    def html_footer(self, site_name: str) -> str:
        """Generate shared footer (year from self.footer_year — no clock reads)."""
        year = f"{escape_html(self.footer_year)} " if self.footer_year else ""
        return f"""  <footer class="site-footer">&copy; {year}{escape_html(site_name)}</footer>
</div>"""

    def html_hero(self, site_name: str) -> str:
        """Generate hero section for index page."""
        return f"""  <section class="hero">
    <h2 class="hero-title">{escape_html(site_name)}</h2>
    <p class="hero-subtitle">Welcome to {escape_html(site_name)}</p>
  </section>"""

    @abstractmethod
    def render_css(self) -> str:
        """Generate complete CSS for this template. Includes reset, typography, components."""
        pass

    def _chrome(self, title, site_name, branding, media_base, nav, base_path, main,
                meta_description="", meta_image="", hero=False) -> str:
        head = self.html_head(title, site_name, branding, media_base, base_path,
                              meta_description=meta_description, meta_image=meta_image)
        parts = [self.html_header(site_name, branding, media_base, nav)]
        if hero:
            parts.append(self.html_hero(site_name))
        parts.append(f'  <main class="main-content">\n{main}\n  </main>')
        parts.append(self.html_footer(site_name))
        return _document(head, "\n".join(parts))

    def render_index(
        self,
        site_name: str,
        pages: list,
        posts: list,
        events: list,
        branding: dict,
        media_base: str,
        has_media: bool = False,
        base_path: str = "",
        meta_description: str = "",
        meta_image: str = "",
    ) -> str:
        """Render index.html."""
        sb = base_path.rstrip("/")
        nav = nav_links(pages, bool(posts), bool(events), has_media, base_path=base_path)
        links = ""
        for p in pages:
            path = (p.get("path") or "").strip().strip("/")
            if path:
                links += f'    <li><a href="{sb}/{escape_html(path)}/">{escape_html(p.get("title") or path)}</a></li>\n'
        if posts:
            links += f'    <li><a href="{sb}/blog/">Blog</a></li>\n'
        if events:
            links += f'    <li><a href="{sb}/events/">Events</a></li>\n'
        if has_media:
            links += f'    <li><a href="{sb}/gallery/">Gallery</a></li>\n'
        items = _list_or(links, "    <li>No pages yet.</li>\n")
        main = f'    <nav class="page-nav"><ul>\n{items}    </ul></nav>'
        return self._chrome(site_name, site_name, branding, media_base, nav, base_path, main,
                            meta_description, meta_image, hero=True)

    def render_page(
        self,
        path: str,
        title: str,
        body: str,
        site_name: str,
        branding: dict,
        media_base: str,
        nav: str,
        tenant_slug: str = "",
        site_id: str = "",
        base_path: str = "",
        meta_description: str = "",
        meta_image: str = "",
    ) -> str:
        """Render a single page (body is rich text → sanitized)."""
        body_rewritten = (
            rewrite_body_media_urls(body, tenant_slug, site_id, media_base)
            if tenant_slug and site_id
            else (body or "")
        )
        main = (
            f'    <h2 class="page-title">{escape_html(title or path)}</h2>\n'
            f'    <div class="content">{sanitize_html(body_rewritten)}</div>'
        )
        return self._chrome(title or path, site_name, branding, media_base, nav, base_path, main,
                            meta_description, meta_image)

    def render_blog_index(
        self,
        site_name: str,
        posts: list,
        branding: dict,
        media_base: str,
        nav: str,
        base_path: str = "",
    ) -> str:
        """Render /blog/ index."""
        sb = base_path.rstrip("/")
        items = "".join(
            f'    <li><a href="{sb}/posts/{escape_html(p.get("slug", ""))}/">'
            f'{escape_html(p.get("title") or p.get("slug", ""))}</a></li>\n'
            for p in posts
        )
        items = _list_or(items, "    <li>No posts yet.</li>\n")
        main = f'    <h2 class="page-title">Blog</h2>\n    <ul class="posts-list">\n{items}    </ul>'
        return self._chrome("Blog", site_name, branding, media_base, nav, base_path, main)

    def render_post_detail(
        self,
        post: dict,
        site_name: str,
        branding: dict,
        media_base: str,
        nav: str,
        tenant_slug: str = "",
        site_id: str = "",
        base_path: str = "",
    ) -> str:
        """Render /posts/{slug}/ detail (body is rich text → sanitized)."""
        body = post.get("body", "") or ""
        body_rewritten = (
            rewrite_body_media_urls(body, tenant_slug, site_id, media_base)
            if tenant_slug and site_id
            else body
        )
        meta_desc = post.get("excerpt") or _plain_text(sanitize_html(body))
        meta_img = media_url(post.get("featured_image_s3_key", ""), media_base) if post.get("featured_image_s3_key") else ""
        main = (
            f'    <h2 class="page-title">{escape_html(post.get("title", ""))}</h2>\n'
            f'    <div class="content post-body">{sanitize_html(body_rewritten)}</div>'
        )
        return self._chrome(post.get("title", ""), site_name, branding, media_base, nav, base_path, main,
                            meta_desc, meta_img)

    def render_events(
        self,
        site_name: str,
        events: list,
        branding: dict,
        media_base: str,
        nav: str,
        base_path: str = "",
    ) -> str:
        """Render /events/ page."""
        items = "".join(
            f'    <li><strong>{escape_html(e.get("title", ""))}</strong> — {escape_html(e.get("event_date", ""))}'
            + (f' @ {escape_html(e.get("venue", ""))}' if e.get("venue") else "")
            + "</li>\n"
            for e in events
        )
        items = _list_or(items, "    <li>No events yet.</li>\n")
        main = f'    <h2 class="page-title">Events</h2>\n    <ul class="events-list">\n{items}    </ul>'
        return self._chrome("Events", site_name, branding, media_base, nav, base_path, main)

    def render_gallery(
        self,
        site_name: str,
        media: list,
        branding: dict,
        media_base: str,
        nav: str,
        base_path: str = "",
    ) -> str:
        """Render /gallery/ page."""
        items = "".join(
            f'    <figure><img src="{escape_html(media_url(m.get("s3_key", ""), media_base))}" '
            f'alt="{escape_html(m.get("caption", ""))}"><figcaption>{escape_html(m.get("caption", ""))}</figcaption></figure>\n'
            for m in media
        )
        items = _list_or(items, "    <p>No media yet.</p>\n")
        main = f'    <h2 class="page-title">Gallery</h2>\n    <div class="media-gallery">\n{items}    </div>'
        return self._chrome("Gallery", site_name, branding, media_base, nav, base_path, main)

    def render_404(
        self,
        site_name: str,
        branding: dict,
        media_base: str,
        nav: str,
        base_path: str = "",
    ) -> str:
        """Render template-aware 404 page (Task 1.127)."""
        sb = base_path.rstrip("/")
        main = (
            '    <h2 class="page-title">Page not found</h2>\n'
            '    <p>The page you requested could not be found.</p>\n'
            f'    <p><a href="{sb}/">Return to home</a></p>'
        )
        return self._chrome("Page not found", site_name, branding, media_base, nav, base_path, main)
