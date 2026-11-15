"""Structured block documents (ADR-0003): pure validation + Python rendering of page `doc`s."""

from .catalog import (
    BLOCKS, MAX_BLOCKS, MAX_DEPTH, MAX_DOC_BYTES, SCHEMA_VERSION, BlockSpec, legacy_doc, load_doc, render_doc,
    validate_doc,
)
from .core import DocValidationError, RenderContext, link_href, normalize_own_links, rewrite_internal_hrefs

__all__ = [
    "BLOCKS", "BlockSpec", "DocValidationError", "MAX_BLOCKS", "MAX_DEPTH", "MAX_DOC_BYTES",
    "RenderContext", "SCHEMA_VERSION", "legacy_doc", "link_href", "load_doc", "normalize_own_links", "render_doc",
    "rewrite_internal_hrefs", "validate_doc",
]
