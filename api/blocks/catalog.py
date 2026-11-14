"""Block catalog v1, validate_doc and render_doc (ADR-0003 §1-4).

Every text prop is escaped, richtext goes through sanitize_html (unchanged allowlist), media
resolves only against snapshot media, links only via link_href. Pure: no I/O, env or clock.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote

from html_sanitizer import sanitize_html
from templates.base_layout import escape_html, legacy_content_html, rewrite_body_media_urls

from .core import (
    DocValidationError, RenderContext, Validator, anchor, boolean, enum, integer, link, list_of,
    media, media_src, obj, rewrite_internal_hrefs, richtext, text,
)

SCHEMA_VERSION = 1
MAX_DEPTH = 3
MAX_BLOCKS = 200
MAX_DOC_BYTES = 256 * 1024
SLOTS = ("col_0", "col_1", "col_2")


@dataclass(frozen=True)
class BlockSpec:
    fields: dict[str, Validator]
    render_fn: Callable[[dict, RenderContext], str]
    post: Callable[[dict, str], dict] | None = None  # cross-prop checks / normalization
    slots: tuple[str, ...] = ()                      # child-block lists (validated by validate_doc)

    def validate(self, props, path: str = "props") -> dict:
        """Validate and normalize non-slot props (unknown props rejected)."""
        if not isinstance(props, dict):
            raise DocValidationError(path, "must be an object")
        for key in props:
            if key != "id" and key not in self.fields and key not in self.slots:
                raise DocValidationError(f"{path}.{key}", "unknown prop")
        out = {"id": _id(props.get("id"), f"{path}.id")}
        out.update({k: v(props.get(k), f"{path}.{k}") for k, v in self.fields.items()})
        return self.post(out, path) if self.post else out

    def render(self, props: dict, rctx: RenderContext) -> str:
        return self.render_fn(props, rctx)


_id = text(64)
_cta = obj({"label": text(100), "link": link})


def _h(cls: str, value: str) -> str:
    return f'<h2 class="{cls}">{escape_html(value)}</h2>' if value else ""


def _img(ref, rctx, cls, alt=None) -> str:
    src, row = media_src(ref, rctx)
    if not src:
        return ""
    alt = alt if alt else row.get("caption", "")
    return f'<img class="{cls}" src="{escape_html(src)}" alt="{escape_html(alt)}">'


# --- renderers -------------------------------------------------------------------------------

def _hero(p, rctx):
    sub = f'<p class="b-hero__subheading">{escape_html(p["subheading"])}</p>' if p["subheading"] else ""
    cta = p["cta"] or {}
    return (f'<section class="b-hero b-hero--{p["align"]}">{_img(p["image"], rctx, "b-hero__image")}'
            f'{_h("b-hero__heading", p["heading"])}{sub}'
            f'{anchor(cta.get("link"), cta.get("label"), rctx, "b-button b-hero__cta")}</section>')


def _richtext_post(p, path):
    if not p["legacy"]:
        p["html"] = sanitize_html(p["html"])
    return p


def _richtext(p, rctx):
    if p["legacy"]:
        # The raw-HTML block: exactly TemplateRenderer.render_page's legacy body (byte-identical).
        return legacy_content_html(p["html"], rctx.tenant_slug, rctx.site_id, rctx.media_base)
    body = rewrite_body_media_urls(p["html"], rctx.tenant_slug, rctx.site_id, rctx.media_base)
    return f'<div class="b-richtext content">{rewrite_internal_hrefs(sanitize_html(body), rctx.base_path)}</div>'


def _image(p, rctx):
    img = _img(p["image"], rctx, "b-image__img", p["alt"])
    if not img:
        return ""
    cap = f'<figcaption>{escape_html(p["caption"])}</figcaption>' if p["caption"] else ""
    return f'<figure class="b-image b-image--{p["size"]}">{img}{cap}</figure>'


def _gallery(p, rctx):
    refs = [{"media_id": k} for k in rctx.media] if p["source"] == "all" else p["items"]
    figs = "".join(f"<figure>{img}</figure>" for r in refs if (img := _img(r, rctx, "b-gallery__img")))
    return f'<div class="b-gallery b-gallery--{p["columns"]}">{figs}</div>' if figs else ""


def _columns(p, rctx, depth=1, budget=None):
    budget = [MAX_BLOCKS] if budget is None else budget
    cols = "".join(f'<div class="b-columns__col">{_render_list(p.get(s), rctx, depth + 1, budget)}</div>'
                   for s in SLOTS[: p["count"]])
    return f'<div class="b-columns b-columns--{p["count"]}">{cols}</div>'


def _cta_block(p, rctx):
    txt = f'<p class="b-cta__text">{escape_html(p["text"])}</p>' if p["text"] else ""
    btn = p["button"] or {}
    return (f'<section class="b-cta b-cta--{p["variant"]}">{_h("b-cta__heading", p["heading"])}{txt}'
            f'{anchor(btn.get("link"), btn.get("label"), rctx, "b-button")}</section>')


def _post_list(p, rctx):
    posts = sorted(rctx.posts, key=lambda x: str(x.get("published_at") or x.get("created_at") or ""),
                   reverse=True)[: p["count"]]
    base = rctx.base_path.rstrip("/")
    items = "".join(
        f'<li><a href="{base}/posts/{escape_html(x["slug"])}/">{escape_html(x.get("title") or x["slug"])}</a>'
        + (f'<p class="b-postlist__excerpt">{escape_html(x["excerpt"])}</p>' if x.get("excerpt") else "")
        + "</li>"
        for x in posts
    )
    body = f'<ul class="b-postlist__list">{items}</ul>' if items else '<p class="b-postlist__empty">No posts yet.</p>'
    return f'<section class="b-postlist">{_h("b-postlist__heading", p["heading"])}{body}</section>'


def _event_list(p, rctx):
    # Pure: no clock. Events sorted by their date string, first N (handler filters past events if needed).
    events = sorted(rctx.events, key=lambda e: str(e.get("event_date") or ""))[: p["count"]]
    items = "".join(
        f'<li><strong>{escape_html(e.get("title", ""))}</strong> '
        f'<span class="b-eventlist__date">{escape_html(e.get("event_date", ""))}</span>'
        + (f' <span class="b-eventlist__venue">{escape_html(e["venue"])}</span>' if e.get("venue") else "")
        + "</li>"
        for e in events
    )
    body = f'<ul class="b-eventlist__list">{items}</ul>' if items else '<p class="b-eventlist__empty">No events yet.</p>'
    return f'<section class="b-eventlist">{_h("b-eventlist__heading", p["heading"])}{body}</section>'


def _link_list(p, rctx):
    items = "".join(f"<li>{a}</li>" for it in p["items"]
                    if (a := anchor(it["link"], it["label"], rctx, "b-linklist__link")))
    if not items:
        return ""
    return f'<nav class="b-linklist">{_h("b-linklist__heading", p["heading"])}<ul>{items}</ul></nav>'


# Embed: provider allowlist; the iframe is a fixed Python template, never user HTML or URLs.
_EMBED_PATTERNS = {
    "youtube": r"[A-Za-z0-9_-]{11}",
    "vimeo": r"[0-9]{1,12}",
    "google_maps": r"[^\x00-\x1f\x7f<>\"`\\]{1,200}",
}
_EMBED_URLS = {
    "youtube": "https://www.youtube-nocookie.com/embed/{}",
    "vimeo": "https://player.vimeo.com/video/{}",
    "google_maps": "https://www.google.com/maps?q={}&output=embed",
}


def _embed_post(p, path):
    if not re.fullmatch(_EMBED_PATTERNS[p["provider"]], p["embed_id"]):
        raise DocValidationError(f"{path}.embed_id", f"invalid {p['provider']} id")
    return p


def _embed(p, rctx):
    src = _EMBED_URLS[p["provider"]].format(quote(p["embed_id"], safe=""))
    title = escape_html(p["title"] or p["provider"].replace("_", " ").title())
    return (f'<div class="b-embed b-embed--{p["provider"]}"><iframe class="b-embed__frame" src="{escape_html(src)}" '
            f'title="{title}" loading="lazy" referrerpolicy="strict-origin-when-cross-origin" '
            f'sandbox="allow-scripts allow-same-origin allow-presentation allow-popups" allowfullscreen>'
            f'</iframe></div>')


BLOCKS: dict[str, BlockSpec] = {
    "Hero": BlockSpec({"heading": text(200), "subheading": text(500), "image": media, "cta": _cta,
                       "align": enum("center", "left")}, _hero),
    "RichText": BlockSpec({"html": richtext, "legacy": boolean}, _richtext, post=_richtext_post),
    "Image": BlockSpec({"image": media, "alt": text(300), "caption": text(500),
                        "size": enum("full", "medium", "small")}, _image),
    "Gallery": BlockSpec({"source": enum("selected", "all"), "items": list_of(media, 100),
                          "columns": integer(2, 4, 3)}, _gallery),
    "Columns": BlockSpec({"count": integer(2, 3, 2)}, _columns, slots=SLOTS),
    "CallToAction": BlockSpec({"heading": text(200), "text": text(1000), "button": _cta,
                               "variant": enum("primary", "secondary")}, _cta_block),
    "Divider": BlockSpec({}, lambda p, r: '<hr class="b-divider">'),
    "Spacer": BlockSpec({"size": enum("md", "sm", "lg")},
                        lambda p, r: f'<div class="b-spacer b-spacer--{p["size"]}" aria-hidden="true"></div>'),
    "PostList": BlockSpec({"heading": text(200), "count": integer(1, 20, 5)}, _post_list),
    "EventList": BlockSpec({"heading": text(200), "count": integer(1, 20, 5)}, _event_list),
    "LinkList": BlockSpec({"heading": text(200),
                           "items": list_of(obj({"label": text(100), "link": link}, nullable=False), 50)}, _link_list),
    "Embed": BlockSpec({"provider": enum(*_EMBED_PATTERNS), "embed_id": text(200), "title": text(200)},
                       _embed, post=_embed_post),
}


# --- documents -------------------------------------------------------------------------------

def load_doc(doc) -> dict:
    """Parse a stored doc (JSON string) or accept an in-process dict; strings over the cap fail."""
    if isinstance(doc, (str, bytes)):
        raw = doc.encode() if isinstance(doc, str) else doc
        if len(raw) > MAX_DOC_BYTES:
            raise DocValidationError("", "doc larger than 256 KB")
        try:
            doc = json.loads(raw)
        except ValueError:
            raise DocValidationError("", "doc is not valid JSON") from None
    if not isinstance(doc, dict):
        raise DocValidationError("", "doc must be an object")
    return doc


_root_props = obj({"title": text(200), "meta_description": text(300)}, nullable=False)


def validate_doc(doc) -> dict:
    """Strict save-time validation. Returns the normalized doc (richtext sanitized).

    Raises DocValidationError (a ValueError) with ``.path`` for unknown schema/type/prop,
    depth > 3, > 200 blocks, or > 256 KB serialized.
    """
    doc = load_doc(doc)
    if len(json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode()) > MAX_DOC_BYTES:
        raise DocValidationError("", "doc larger than 256 KB")
    for key in doc:
        if key not in ("schema", "root", "content"):
            raise DocValidationError(key, "unknown key")
    if doc.get("schema") != SCHEMA_VERSION:
        raise DocValidationError("schema", f"unsupported schema (expected {SCHEMA_VERSION})")
    root = doc.get("root") or {}
    if not isinstance(root, dict) or set(root) - {"props"}:
        raise DocValidationError("root", "root must be {props}")
    count = [0]

    def blocks(items, path, depth):
        if not isinstance(items, list):
            raise DocValidationError(path, "must be a list of blocks")
        out = []
        for i, b in enumerate(items):
            bp = f"{path}[{i}]"
            if depth > MAX_DEPTH:
                raise DocValidationError(bp, f"nesting deeper than {MAX_DEPTH}")
            count[0] += 1
            if count[0] > MAX_BLOCKS:
                raise DocValidationError(bp, f"more than {MAX_BLOCKS} blocks")
            if not isinstance(b, dict) or set(b) - {"type", "props"}:
                raise DocValidationError(bp, "block must be {type, props}")
            spec = BLOCKS.get(b.get("type"))
            if spec is None:
                raise DocValidationError(f"{bp}.type", f"unknown block type {b.get('type')!r}")
            raw = b.get("props") or {}
            props = spec.validate(raw, f"{bp}.props")
            for s in spec.slots:
                props[s] = blocks(raw.get(s) or [], f"{bp}.props.{s}", depth + 1)
            out.append({"type": b["type"], "props": props})
        return out

    return {
        "schema": SCHEMA_VERSION,
        "root": {"props": _root_props(root.get("props") or {}, "root.props")},
        "content": blocks(doc.get("content") or [], "content", 1),
    }


def _render_list(items, rctx: RenderContext, depth: int, budget: list) -> str:
    out = []
    for b in items if isinstance(items, list) else []:
        if depth > MAX_DEPTH or budget[0] <= 0:
            break
        spec = BLOCKS.get(b.get("type")) if isinstance(b, dict) else None
        if spec is None:
            continue  # unknown block: skipped on compile
        budget[0] -= 1
        raw = b.get("props") if isinstance(b.get("props"), dict) else {}
        try:
            props = spec.validate({k: v for k, v in raw.items() if k == "id" or k in spec.fields})
        except DocValidationError:
            continue  # invalid props: skipped (the save path rejects them)
        if spec.slots:
            html = _columns({**props, **{s: raw.get(s) for s in spec.slots}}, rctx, depth, budget)
        else:
            html = spec.render(props, rctx)
        if html:
            out.append(html)
    return "\n".join(out)


def render_doc(doc, rctx: RenderContext) -> str:
    """Render a block doc to main-column HTML. Lenient: unknown/invalid blocks and unknown props
    are skipped; caps (depth 3, 200 blocks, 256 KB stored JSON) still bound the work."""
    try:
        doc = load_doc(doc)
    except DocValidationError:
        return ""
    return _render_list(doc.get("content"), rctx, 1, [MAX_BLOCKS])


def legacy_doc(body: str) -> dict:
    """A page without ``doc``: one raw-HTML RichText block (renders byte-identically to today)."""
    html = body if isinstance(body, str) else ""
    return {"schema": SCHEMA_VERSION, "root": {"props": {}},
            "content": [{"type": "RichText", "props": {"html": html, "legacy": True}}]}
