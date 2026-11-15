"""Block-core primitives (ADR-0003 §1-3): RenderContext, closed prop types, links.

Pure: no boto3, env, clock or randomness (enforced by tests/test_blocks.py AST test).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from html_sanitizer import _is_dangerous_url
from templates.base_layout import escape_html, media_url


class DocValidationError(ValueError):
    """Invalid block doc. ``path`` locates the offending node, e.g. ``content[1].props.col_0[0]``."""

    def __init__(self, path: str, message: str):
        super().__init__(f"{path}: {message}" if path else message)
        self.path = path
        self.message = message


@dataclass(frozen=True)
class RenderContext:
    base_path: str = ""                 # "" live, "/preview" draft
    media_base: str = "/media/"
    tenant_slug: str = ""
    site_id: str = ""
    media: Mapping[str, dict] = field(default_factory=dict)   # media id -> media row
    pages: Mapping[str, dict] = field(default_factory=dict)   # path -> page row
    posts: tuple = ()                   # post rows (with non-empty slug)
    events: tuple = ()
    tokens: Mapping[str, str] = field(default_factory=dict)  # template tokens (T-32)

    @classmethod
    def build(cls, *, base_path="", media_base="/media/", tenant_slug="", site_id="",
              media=(), pages=(), posts=(), events=(), tokens=None) -> "RenderContext":
        """Index snapshot lists (same path/slug normalization as compile_site)."""
        page_index = {}
        for p in pages:
            path = (p.get("path") or "").strip().strip("/")
            if path:
                page_index[path] = p
        return cls(
            base_path=base_path,
            media_base=media_base,
            tenant_slug=tenant_slug,
            site_id=site_id,
            media=MappingProxyType({m["id"]: m for m in media if m.get("id")}),
            pages=MappingProxyType(page_index),
            posts=tuple({**p, "slug": p["slug"].strip()} for p in posts if (p.get("slug") or "").strip()),
            events=tuple(events),
            tokens=MappingProxyType(dict(tokens or {})),
        )


# --- links -----------------------------------------------------------------------------------

LINK_KINDS = ("home", "page", "post", "blog", "events", "gallery", "external")
_PATH_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,99}$")
_EXTERNAL_SCHEMES = ("http://", "https://", "mailto:")


def _external_ok(url: str) -> bool:
    return (
        url.lower().startswith(_EXTERNAL_SCHEMES)
        and not _is_dangerous_url(url)
        and not re.search(r"[\s\x00-\x1f\x7f<>\"'`\\]", url)
        and len(url) <= 2048
    )


def link_href(link: Mapping | None, base_path: str = "") -> str:
    """Href for a link prop: root-relative internal links prefixed with base_path; "" if invalid."""
    if not isinstance(link, Mapping):
        return ""
    base = (base_path or "").rstrip("/")
    kind, path = link.get("kind"), link.get("path") or ""
    if kind == "home":
        return f"{base}/"
    if kind in ("blog", "events", "gallery"):
        return f"{base}/{kind}/"
    if kind in ("page", "post") and _PATH_RE.match(path):
        return f"{base}/{path}/" if kind == "page" else f"{base}/posts/{path}/"
    if kind == "external":
        url = link.get("url") or ""
        return url if isinstance(url, str) and _external_ok(url) else ""
    return ""


def normalize_own_links(node, hosts, page_paths):
    """Save-time (ADR-0003 §3): external link props pointing at the site's own host become
    internal ``{kind: home}`` (``/``) or ``{kind: page, path}`` (an existing page). Returns a new
    tree; anything else (other hosts, query/fragment, unknown paths) is left as is."""
    if isinstance(node, list):
        return [normalize_own_links(x, hosts, page_paths) for x in node]
    if not isinstance(node, dict):
        return node
    if node.get("kind") == "external" and isinstance(node.get("url"), str):
        parts = urlsplit(node["url"])
        host = (parts.hostname or "").lower()
        if parts.scheme in ("http", "https") and host in hosts and not parts.query and not parts.fragment:
            path = parts.path.strip("/")
            if not path:
                return {**node, "kind": "home", "path": "", "url": ""}
            if path in page_paths and _PATH_RE.match(path):
                return {**node, "kind": "page", "path": path, "url": ""}
        return node
    return {k: normalize_own_links(v, hosts, page_paths) for k, v in node.items()}


_HREF_RE = re.compile(r'(\shref=")/(?!/)')


def rewrite_internal_hrefs(html: str, base_path: str) -> str:
    """Prefix root-relative hrefs (``/x``, not ``//x``) in sanitized HTML with base_path."""
    base = (base_path or "").rstrip("/")
    if not base or not html:
        return html or ""
    return _HREF_RE.sub(lambda m: f"{m.group(1)}{base}/", html)


def resolve_href(link: Mapping | None, rctx: RenderContext) -> str:
    """link_href, but internal refs must resolve against the snapshot (pages/posts/sections)."""
    if not isinstance(link, Mapping):
        return ""
    kind, path = link.get("kind"), link.get("path")
    if (kind == "page" and path not in rctx.pages) or (
        kind == "post" and not any(p["slug"] == path for p in rctx.posts)
    ) or (kind == "blog" and not rctx.posts) or (kind == "events" and not rctx.events) or (
        kind == "gallery" and not rctx.media
    ):
        return ""
    return link_href(link, rctx.base_path)


def anchor(link: Mapping | None, label: str, rctx: RenderContext, cls: str) -> str:
    """<a> for a resolved link, or "" when the label is empty or the link does not resolve."""
    href = resolve_href(link, rctx)
    if not href or not label:
        return ""
    extra = ' target="_blank" rel="noopener noreferrer"' if link.get("new_tab") else ""
    return f'<a class="{cls}" href="{escape_html(href)}"{extra}>{escape_html(label)}</a>'


def media_src(ref: Mapping | None, rctx: RenderContext) -> tuple[str, dict | None]:
    """(url, media row) for a media prop; ("", None) unless the id is in this site's snapshot."""
    row = rctx.media.get(ref.get("media_id")) if isinstance(ref, Mapping) else None
    if not row or not row.get("s3_key"):
        return "", None
    return media_url(row["s3_key"], rctx.media_base), row


# --- closed prop types -----------------------------------------------------------------------
# Each type is a validator ``(value, path) -> normalized``; missing / None -> default.

Validator = Callable[[Any, str], Any]
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _fail(path: str, msg: str):
    raise DocValidationError(path, msg)


def text(max_len: int = 500, default: str = "") -> Validator:
    def v(value, path):
        if value is None:
            return default
        if not isinstance(value, str):
            _fail(path, "must be a string")
        if len(value) > max_len:
            _fail(path, f"longer than {max_len} characters")
        return _CTRL_RE.sub("", value)
    return v


def richtext(value, path):
    """HTML string; sanitized by the block (RichText) on validate and again on render."""
    if value is None:
        return ""
    if not isinstance(value, str):
        _fail(path, "must be an HTML string")
    return value


def boolean(value, path):
    if value is None:
        return False
    if not isinstance(value, bool):
        _fail(path, "must be a boolean")
    return value


def enum(*choices: str) -> Validator:
    def v(value, path):
        if value is None:
            return choices[0]
        if value not in choices:
            _fail(path, f"must be one of {', '.join(choices)}")
        return value
    return v


def integer(lo: int, hi: int, default: int) -> Validator:
    def v(value, path):
        if value is None:
            return default
        if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
            _fail(path, f"must be an integer {lo}-{hi}")
        return value
    return v


def obj(fields: dict[str, Validator], nullable: bool = True) -> Validator:
    def v(value, path):
        if value is None and nullable:
            return None
        if not isinstance(value, Mapping):
            _fail(path, "must be an object")
        for key in value:
            if key not in fields:
                _fail(f"{path}.{key}", "unknown prop")
        return {k: fv(value.get(k), f"{path}.{k}") for k, fv in fields.items()}
    return v


def list_of(item: Validator, max_items: int) -> Validator:
    def v(value, path):
        if value is None:
            return []
        if not isinstance(value, list):
            _fail(path, "must be a list")
        if len(value) > max_items:
            _fail(path, f"more than {max_items} items")
        return [item(x, f"{path}[{i}]") for i, x in enumerate(value)]
    return v


_media_id = text(64)


def media(value, path):
    """``{media_id}`` reference, resolved against snapshot media at render (never a URL)."""
    out = obj({"media_id": _media_id})(value, path)
    return out if out and out["media_id"] else None


_link_fields = obj({"kind": enum(*LINK_KINDS), "path": text(100), "url": text(2048), "new_tab": boolean})


def link(value, path):
    """``{kind: home|page|post|blog|events|gallery, path?}`` or ``{kind: external, url}``."""
    out = _link_fields(value, path)
    if out is None:
        return None
    if out["kind"] in ("page", "post") and not _PATH_RE.match(out["path"]):
        _fail(f"{path}.path", "invalid path")
    if out["kind"] == "external" and not _external_ok(out["url"]):
        _fail(f"{path}.url", "external links must be http(s):// or mailto:")
    return out
