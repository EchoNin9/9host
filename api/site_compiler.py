"""
SiteCompiler — pure static-site compilation (docs/SPEC.md §3 Module 4).

compile_site(snapshot, mode) turns a SiteSnapshot into a CompiledSiteBundle of
UTF-8 files. No boto3, no I/O, no clock or env reads: identical snapshots yield
identical bundles.

- live:  internal links are root-relative (/, /blog/, /posts/{slug}/, /events/, /gallery/),
         plus style.css, 404.html, sitemap.xml, robots.txt.
- draft: links are prefixed with /preview, CSS is inlined (draft assets need the
         preview token), and a small script propagates ?token= to /preview links.
Rich-text bodies are sanitized by the template renderers (Bug #8 stored XSS).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal

from templates import get_renderer
from templates.base_layout import escape_html, media_url, nav_links

LIVE_BASE_PATH = ""
DRAFT_BASE_PATH = "/preview"
DEFAULT_TEMPLATE = "business-generic"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}

# Platform script (not user content): carries ?token= across /preview navigation.
_DRAFT_TOKEN_SCRIPT = """<script>
(function(){var t=new URLSearchParams(location.search).get("token");if(t){document.querySelectorAll("a[href]").forEach(function(a){try{var u=new URL(a.href,location.origin);if(u.origin===location.origin&&u.pathname.startsWith("/preview")){u.searchParams.set("token",t);a.href=u.pathname+u.search}}catch(e){}})}})();
</script>
"""


@dataclass(frozen=True)
class SiteSnapshot:
    tenant_slug: str
    site_id: str
    site: dict
    template: dict
    pages: list[dict]
    posts: list[dict]
    events: list[dict]
    media: list[dict]
    # Inputs the handler resolves outside the pure core (clock / env):
    generated_at: str = ""          # ISO timestamp; drives footer year + manifest
    media_base: str = "/media/"     # CLOUDFRONT_MEDIA_URL
    base_domain: str = "echo9.net"  # first of DOMAINS, for sitemap/robots


@dataclass(frozen=True)
class CompiledSiteBundle:
    files: dict[str, bytes]        # relative path (e.g. "index.html", "blog/index.html") -> UTF-8 bytes
    content_types: dict[str, str]  # relative path -> MIME type
    manifest: dict = field(default_factory=dict)


def content_type_for(path: str) -> str:
    for ext, ctype in CONTENT_TYPES.items():
        if path.endswith(ext):
            return ctype
    return "application/octet-stream"


def _renderer_for(template: dict):
    # Forked templates inherit their base layout via forked_from.
    slug = ((template or {}).get("forked_from") or (template or {}).get("slug") or "").strip().lower()
    renderer = get_renderer(slug) or get_renderer(DEFAULT_TEMPLATE)
    if renderer is None:
        raise ValueError(f"No renderer for template: {slug}")
    return renderer


def _sitemap(base_url: str, pages: list, posts: list, has_events: bool, has_media: bool) -> str:
    urls = [base_url + "/"]
    urls += [f"{base_url}/{p['path']}/" for p in pages]
    if posts:
        urls.append(f"{base_url}/blog/")
        urls += [f"{base_url}/posts/{p['slug']}/" for p in posts]
    if has_events:
        urls.append(f"{base_url}/events/")
    if has_media:
        urls.append(f"{base_url}/gallery/")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines += [f"  <url><loc>{escape_html(u)}</loc></url>" for u in urls]
    lines.append("</urlset>")
    return "\n".join(lines)


def compile_site(snapshot: SiteSnapshot, mode: Literal["live", "draft"] = "live") -> CompiledSiteBundle:
    if mode not in ("live", "draft"):
        raise ValueError(f"mode must be 'live' or 'draft', got {mode!r}")
    live = mode == "live"
    base_path = LIVE_BASE_PATH if live else DRAFT_BASE_PATH

    renderer = _renderer_for(snapshot.template)
    renderer.footer_year = (snapshot.generated_at or "")[:4]

    site = snapshot.site or {}
    site_name = site.get("name") or "Site"
    branding = site.get("branding") if isinstance(site.get("branding"), dict) else {}
    media_base = snapshot.media_base
    tenant, site_id = snapshot.tenant_slug, snapshot.site_id

    pages = []
    for p in snapshot.pages:
        path = (p.get("path") or "").strip().strip("/")
        if path:
            pages.append({**p, "path": path})
    posts = [{**p, "slug": (p.get("slug") or "").strip()} for p in snapshot.posts if (p.get("slug") or "").strip()]
    events = list(snapshot.events)
    media = list(snapshot.media)

    nav = nav_links(pages, bool(posts), bool(events), bool(media), base_path=base_path)
    pages_html: dict[str, str] = {}

    meta_image = media_url(branding.get("logo_s3_key", ""), media_base) if branding.get("logo_s3_key") else ""
    pages_html["index.html"] = renderer.render_index(
        site_name, pages, posts, events, branding, media_base, bool(media), base_path=base_path,
        meta_description=site_name, meta_image=meta_image,
    )
    for p in pages:
        pages_html[f"{p['path']}/index.html"] = renderer.render_page(
            p["path"], p.get("title", ""), p.get("body", ""), site_name, branding, media_base, nav,
            tenant, site_id, base_path=base_path,
        )
    if posts:
        pages_html["blog/index.html"] = renderer.render_blog_index(
            site_name, posts, branding, media_base, nav, base_path=base_path,
        )
    for post in posts:
        pages_html[f"posts/{post['slug']}/index.html"] = renderer.render_post_detail(
            post, site_name, branding, media_base, nav, tenant, site_id, base_path=base_path,
        )
    if events:
        pages_html["events/index.html"] = renderer.render_events(
            site_name, events, branding, media_base, nav, base_path=base_path,
        )
    if media:
        pages_html["gallery/index.html"] = renderer.render_gallery(
            site_name, media, branding, media_base, nav, base_path=base_path,
        )
    pages_html["404.html"] = renderer.render_404(site_name, branding, media_base, nav, base_path=base_path)

    text_files: dict[str, str] = {}
    css = renderer.render_css()
    if live:
        text_files["style.css"] = css
        text_files.update(pages_html)
        site_slug = (site.get("slug") or "").strip() or "site"
        base_url = f"https://{site_slug}.{snapshot.base_domain}"
        text_files["sitemap.xml"] = _sitemap(base_url, pages, posts, bool(events), bool(media))
        text_files["robots.txt"] = f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n"
    else:
        # /preview/style.css can't load without a token, so inline it; append token script.
        css_link = f'<link rel="stylesheet" href="{DRAFT_BASE_PATH}/style.css">'
        style_block = f"<style>\n{css}\n</style>"
        for path, html in pages_html.items():
            html = html.replace(css_link, style_block, 1)
            i = html.rfind("</body>")
            text_files[path] = html[:i] + _DRAFT_TOKEN_SCRIPT + html[i:]

    files = {path: text.encode("utf-8") for path, text in text_files.items()}
    manifest = {
        "mode": mode,
        "generated_at": snapshot.generated_at,
        "files": [
            {"path": path, "sha256": hashlib.sha256(body).hexdigest(), "size": len(body)}
            for path, body in files.items()
        ],
    }
    return CompiledSiteBundle(
        files=files,
        content_types={path: content_type_for(path) for path in files},
        manifest=manifest,
    )
