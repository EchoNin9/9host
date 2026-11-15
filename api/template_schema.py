"""
Platform template data validation (ADR-0003 §5, T-32a). Pure: no boto3, clock or env reads.

A template is a head (metadata + version pointers) plus immutable versions. Superadmins author
data only: tokens (regex-allowlisted, the same patterns as branding_styles), the allowed block
subset, preset block docs, and limited header/footer config. Never HTML or CSS.
"""

from __future__ import annotations

import json

from blocks import BLOCKS, DocValidationError, validate_doc
from blocks.core import enum, link, list_of, obj, text
from middleware import validate_slug_format
from reserved_slugs import HOME_PAGE_PATH, RESERVED_PAGE_PATHS
from templates import TEMPLATE_RENDERERS
from templates.base_layout import TEMPLATE_TOKENS
from tier_config import is_valid_tier

TEMPLATE_SCHEMA = 1
NAV_STYLES = ("default", "centered", "minimal")
VERSION_FIELDS = ("tokens", "allowed_blocks", "page_presets", "header", "footer")
MAX_PRESETS = 20
# Paths the compiler generates itself (blog/index.html, posts/*, events/, gallery/): a page there
# would collide, so presets may not use them.
GENERATED_PATHS = frozenset({"blog", "posts", "events", "gallery"})

_header = obj({"show_logo": lambda v, p: True if v is None else _bool(v, p), "nav_style": enum(*NAV_STYLES)},
              nullable=False)
_footer = obj({"text": text(500),
               "links": list_of(obj({"label": text(100), "link": link}, nullable=False), 20)}, nullable=False)


def _bool(value, path):
    if not isinstance(value, bool):
        raise DocValidationError(path, "must be a boolean")
    return value


def validate_template_slug(slug) -> str | None:
    """Error message for an invalid template slug (lowercase alnum + hyphen; never '#'), else None."""
    if not isinstance(slug, str) or slug != slug.strip().lower() or len(slug) > 64:
        return "slug must be lowercase alphanumeric + hyphen (max 64)."
    return validate_slug_format(slug, "slug")


def validate_base_renderer(name) -> str:
    if name not in TEMPLATE_RENDERERS:
        raise DocValidationError("base_renderer", f"must be one of {', '.join(sorted(TEMPLATE_RENDERERS))}")
    return name


def validate_tokens(tokens) -> dict:
    """{primary, secondary, bg, text, heading_font, body_font, radius, spacing}; all optional."""
    if tokens is None:
        return {}
    if not isinstance(tokens, dict):
        raise DocValidationError("tokens", "must be an object")
    out = {}
    for key, value in tokens.items():
        if key not in TEMPLATE_TOKENS:
            raise DocValidationError(f"tokens.{key}", "unknown token")
        if value in (None, ""):
            continue
        if not isinstance(value, str) or not TEMPLATE_TOKENS[key][0].match(value):
            raise DocValidationError(f"tokens.{key}", "invalid value")
        out[key] = value
    return out


def validate_allowed_blocks(allowed) -> dict:
    """Subset of the block catalog: {name: true | tier}. A list means all true. Tier gating is
    stored, not enforced (T-34). None = the whole catalog."""
    if allowed is None:
        return {name: True for name in BLOCKS}
    if isinstance(allowed, list):
        allowed = {name: True for name in allowed}
    if not isinstance(allowed, dict):
        raise DocValidationError("allowed_blocks", "must be an object or list")
    out = {}
    for name, value in allowed.items():
        if name not in BLOCKS:
            raise DocValidationError(f"allowed_blocks.{name}", "unknown block type")
        if value is False:
            continue
        if value is not True and not (isinstance(value, str) and is_valid_tier(value)):
            raise DocValidationError(f"allowed_blocks.{name}", "must be true or a tier")
        out[name] = True if value is True else value.upper()
    return out


def validate_page_presets(presets) -> dict:
    """{path: doc}; path is `_home` or a valid, unreserved page slug; each doc via validate_doc.
    Returns {path: normalized doc dict}."""
    if presets is None:
        return {}
    if not isinstance(presets, dict):
        raise DocValidationError("page_presets", "must be an object")
    if len(presets) > MAX_PRESETS:
        raise DocValidationError("page_presets", f"more than {MAX_PRESETS} presets")
    out = {}
    for path, doc in presets.items():
        if path != HOME_PAGE_PATH and (validate_slug_format(path, "path") or path != path.lower()
                                       or path in RESERVED_PAGE_PATHS or path in GENERATED_PATHS):
            raise DocValidationError(f"page_presets.{path}", "invalid page path")
        try:
            out[path] = validate_doc(doc)
        except DocValidationError as e:
            raise DocValidationError(f"page_presets.{path}.{e.path}".rstrip("."), e.message) from None
    return out


def validate_version(body: dict) -> dict:
    """Normalize a version payload (VERSION_FIELDS). Raises DocValidationError(path, message)."""
    unknown = set(body) - set(VERSION_FIELDS)
    if unknown:
        raise DocValidationError(sorted(unknown)[0], "unknown field")
    return {
        "schema": TEMPLATE_SCHEMA,
        "tokens": validate_tokens(body.get("tokens")),
        "allowed_blocks": validate_allowed_blocks(body.get("allowed_blocks")),
        "page_presets": validate_page_presets(body.get("page_presets")),
        "header": _header(body.get("header") or {}, "header"),
        "footer": _footer(body.get("footer") or {}, "footer"),
    }


def presets_to_store(presets: dict) -> dict:
    """Preset docs are stored as compact JSON strings (like page `doc`: no Decimal coercion)."""
    return {p: json.dumps(d, separators=(",", ":"), ensure_ascii=False, sort_keys=True) for p, d in presets.items()}


def presets_from_store(presets) -> dict:
    out = {}
    for path, raw in (presets or {}).items():
        try:
            out[path] = json.loads(raw) if isinstance(raw, str) else raw
        except ValueError:
            continue
    return out
