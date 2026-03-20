"""
Base layout and TemplateRenderer (Task 1.112).

Shared HTML structure, branding injection, and utilities.
Template-specific layouts extend TemplateRenderer.
"""

import re
from abc import ABC, abstractmethod


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


def branding_styles(branding: dict) -> str:
    """Generate CSS custom properties from site.branding."""
    if not branding or not isinstance(branding, dict):
        return ""
    parts = []
    if branding.get("primary_color"):
        parts.append(f"  --brand-primary: {escape_html(branding['primary_color'])};")
    if branding.get("secondary_color"):
        parts.append(f"  --brand-secondary: {escape_html(branding['secondary_color'])};")
    if branding.get("font_family"):
        parts.append(f"  --brand-font: {escape_html(branding['font_family'])}, sans-serif;")
    if branding.get("background_color"):
        parts.append(f"  --brand-bg: {escape_html(branding['background_color'])};")
    if branding.get("text_color"):
        parts.append(f"  --brand-text: {escape_html(branding['text_color'])};")
    if not parts:
        return ""
    return "<style>\n:root {\n" + "\n".join(parts) + "\n}\n</style>\n  "


def nav_links(pages: list, has_posts: bool, has_events: bool, has_media: bool = False, site_base: str = "") -> str:
    """Build nav links from pages + blog + events + gallery.

    site_base: URL prefix for all internal links (e.g. '/site/{tenant}/{site_id}').
    Empty string produces root-relative paths.
    """
    base = site_base.rstrip("/")
    links = []
    for p in pages:
        path = (p.get("path") or "").strip()
        if path:
            links.append(f'<li><a href="{base}/{path}/">{escape_html(p.get("title") or path)}</a></li>')
    if has_posts:
        links.append(f'<li><a href="{base}/blog/">Blog</a></li>')
    if has_events:
        links.append(f'<li><a href="{base}/events/">Events</a></li>')
    if has_media:
        links.append(f'<li><a href="{base}/gallery/">Gallery</a></li>')
    return "\n      ".join(links) if links else ""


class TemplateRenderer(ABC):
    """
    Base class for template-specific HTML/CSS rendering.
    Each template implements its own layout and theme.
    """

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
        # base_path: "" for root, "../" for blog/, "../../" for posts/slug/, etc.
        css_href = f"{base_path}style.css" if base_path else "style.css"
        css_link = f'  <link rel="stylesheet" href="{css_href}">'
        meta_parts = []
        if meta_description:
            meta_parts.append(f'  <meta name="description" content="{escape_html(meta_description[:160])}">')
        if meta_image:
            meta_parts.append(f'  <meta property="og:image" content="{escape_html(meta_image)}">')
        meta_parts.append(f'  <meta property="og:title" content="{escape_html(title or site_name)} — {escape_html(site_name)}">')
        meta_block = "\n".join(meta_parts) + "\n" if meta_parts else ""
        return f"""  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape_html(title or site_name)} — {escape_html(site_name)}</title>
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
        """Generate shared footer."""
        from datetime import datetime, timezone
        year = datetime.now(timezone.utc).year
        return f"""  <footer class="site-footer">&copy; {year} {escape_html(site_name)}</footer>
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
        site_base: str = "",
    ) -> str:
        """Render index.html."""
        sb = site_base.rstrip("/")
        nav = nav_links(pages, bool(posts), bool(events), has_media, site_base=site_base)
        links = "".join(
            f'    <li><a href="{sb}/{p["path"]}/">{escape_html(p["title"] or p["path"])}</a></li>\n'
            for p in pages
        )
        if posts:
            links += f'    <li><a href="{sb}/blog/">Blog</a></li>\n'
        if events:
            links += f'    <li><a href="{sb}/events/">Events</a></li>\n'
        if has_media:
            links += f'    <li><a href="{sb}/gallery/">Gallery</a></li>\n'
        head = self.html_head(
            site_name, site_name, branding, media_base, base_path,
            meta_description=meta_description, meta_image=meta_image,
        )
        header = self.html_header(site_name, branding, media_base, nav)
        hero = self.html_hero(site_name)
        footer = self.html_footer(site_name)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
</head>
<body>
{header}
{hero}
  <main class="main-content">
    <nav class="page-nav"><ul>
{links or "    <li>No pages yet.</li>\n"}
    </ul></nav>
  </main>
{footer}
</body>
</html>"""

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
        """Render a single page."""
        body_rewritten = (
            rewrite_body_media_urls(body, tenant_slug, site_id, media_base)
            if tenant_slug and site_id
            else (body or "")
        )
        head = self.html_head(
            title or path, site_name, branding, media_base, base_path,
            meta_description=meta_description, meta_image=meta_image,
        )
        header = self.html_header(site_name, branding, media_base, nav)
        footer = self.html_footer(site_name)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
</head>
<body>
{header}
  <main class="main-content">
    <h2 class="page-title">{escape_html(title or path)}</h2>
    <div class="content">{body_rewritten}</div>
  </main>
{footer}
</body>
</html>"""

    def render_blog_index(
        self,
        site_name: str,
        posts: list,
        branding: dict,
        media_base: str,
        nav: str,
        base_path: str = "",
        site_base: str = "",
    ) -> str:
        """Render /blog/ index."""
        sb = site_base.rstrip("/")
        items = "".join(
            f'    <li><a href="{sb}/posts/{escape_html(p["slug"])}/">{escape_html(p["title"] or p["slug"])}</a></li>\n'
            for p in posts
        )
        head = self.html_head("Blog", site_name, branding, media_base, base_path)
        header = self.html_header(site_name, branding, media_base, nav)
        footer = self.html_footer(site_name)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
</head>
<body>
{header}
  <main class="main-content">
    <h2 class="page-title">Blog</h2>
    <ul class="posts-list">
{items or "    <li>No posts yet.</li>\n"}
    </ul>
  </main>
{footer}
</body>
</html>"""

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
        """Render /posts/{slug}/ detail."""
        body = post.get("body", "")
        body_rewritten = (
            rewrite_body_media_urls(body, tenant_slug, site_id, media_base)
            if tenant_slug and site_id
            else body
        )
        meta_desc = (post.get("excerpt") or post.get("body", ""))[:160] if post else ""
        meta_img = media_url(post.get("featured_image_s3_key", ""), media_base) if post and post.get("featured_image_s3_key") else ""
        head = self.html_head(
            post.get("title", ""), site_name, branding, media_base, base_path,
            meta_description=meta_desc, meta_image=meta_img,
        )
        header = self.html_header(site_name, branding, media_base, nav)
        footer = self.html_footer(site_name)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
</head>
<body>
{header}
  <main class="main-content">
    <h2 class="page-title">{escape_html(post.get("title", ""))}</h2>
    <div class="content post-body">{body_rewritten}</div>
  </main>
{footer}
</body>
</html>"""

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
        head = self.html_head("Events", site_name, branding, media_base, base_path)
        header = self.html_header(site_name, branding, media_base, nav)
        footer = self.html_footer(site_name)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
</head>
<body>
{header}
  <main class="main-content">
    <h2 class="page-title">Events</h2>
    <ul class="events-list">
{items or "    <li>No events yet.</li>\n"}
    </ul>
  </main>
{footer}
</body>
</html>"""

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
            f'    <figure><img src="{escape_html(media_url(m.get("s3_key", ""), media_base))}" alt="{escape_html(m.get("caption", ""))}"><figcaption>{escape_html(m.get("caption", ""))}</figcaption></figure>\n'
            for m in media
        )
        head = self.html_head("Gallery", site_name, branding, media_base, base_path)
        header = self.html_header(site_name, branding, media_base, nav)
        footer = self.html_footer(site_name)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
</head>
<body>
{header}
  <main class="main-content">
    <h2 class="page-title">Gallery</h2>
    <div class="media-gallery">
{items or "    <p>No media yet.</p>\n"}
    </div>
  </main>
{footer}
</body>
</html>"""

    def render_404(
        self,
        site_name: str,
        branding: dict,
        media_base: str,
        nav: str,
        base_path: str = "",
        site_base: str = "",
    ) -> str:
        """Render template-aware 404 page (Task 1.127)."""
        sb = site_base.rstrip("/")
        head = self.html_head("Page not found", site_name, branding, media_base, base_path)
        header = self.html_header(site_name, branding, media_base, nav)
        footer = self.html_footer(site_name)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head}
</head>
<body>
{header}
  <main class="main-content">
    <h2 class="page-title">Page not found</h2>
    <p>The page you requested could not be found.</p>
    <p><a href="{sb}/">Return to home</a></p>
  </main>
{footer}
</body>
</html>"""
