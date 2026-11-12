"""
Pure standard library HTML sanitizer for rich-text content in 9host.
Uses html.parser.HTMLParser to enforce an allowlist of tags and attributes,
strips dangerous tags with their contents, drops event handlers and malicious URLs,
and ensures unclosed tags do not leak.
"""
from __future__ import annotations

import html
import re
import urllib.parse
from html.parser import HTMLParser

# Tags whose entire subtree (tag + contents) must be discarded
STRIP_WITH_CONTENTS = frozenset({
    "script",
    "style",
    "iframe",
    "object",
    "embed",
})

# Allowed rich-text semantic tags
ALLOWED_TAGS = frozenset({
    "p", "br", "strong", "b", "em", "i", "u", "s",
    "a", "ul", "ol", "li",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "code", "pre",
    "img", "figure", "figcaption", "hr",
    "span", "div",
    "table", "thead", "tbody", "tr", "th", "td",
    "sup", "sub",
})

# Void (self-closing) elements in HTML
VOID_TAGS = frozenset({"br", "hr", "img"})

# Allowed attributes per tag (all on* attributes are always dropped)
ALLOWED_ATTRIBUTES = {
    "a": frozenset({"href", "title", "target", "rel"}),
    "img": frozenset({"src", "alt", "title", "width", "height"}),
}

# Dangerous URL schemes that must never appear in href / src
DANGEROUS_SCHEMES = ("javascript:", "vbscript:", "data:text/html")


def _is_dangerous_url(url: str) -> bool:
    """
    Check if a URL uses a dangerous scheme (javascript:, vbscript:, data:text/html).
    Tolerates entity-encoding (e.g. jav&#x09;ascript:), URL-encoding, whitespace,
    and control character obfuscation.
    """
    if not url:
        return False

    # Repeatedly unescape HTML entities (up to 3 levels)
    cleaned = url
    for _ in range(3):
        unescaped = html.unescape(cleaned)
        if unescaped == cleaned:
            break
        cleaned = unescaped

    # Strip whitespace, ASCII control chars, and null bytes
    normalized = re.sub(r"[\s\x00-\x1f\x7f-\x9f]+", "", cleaned).lower()

    # Also check URL-decoded form in case schemes are percent-encoded
    try:
        unquoted = urllib.parse.unquote(normalized)
    except Exception:
        unquoted = normalized

    for scheme in DANGEROUS_SCHEMES:
        if normalized.startswith(scheme) or unquoted.startswith(scheme):
            return True

    return False


class _SanitizingHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self._strip_content_depth: int = 0
        self._open_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()

        # If entering a tag whose content must be stripped
        if tag_lower in STRIP_WITH_CONTENTS:
            self._strip_content_depth += 1
            return

        # If inside a stripped element subtree, ignore everything
        if self._strip_content_depth > 0:
            return

        # If not an allowed tag, drop the tag but keep children/text
        if tag_lower not in ALLOWED_TAGS:
            return

        # Filter and sanitize attributes
        allowed_attr_names = ALLOWED_ATTRIBUTES.get(tag_lower, frozenset())
        clean_attrs: list[tuple[str, str]] = []

        for name, val in attrs:
            if not name:
                continue
            name_lower = name.lower()

            # Universally drop all on* event attributes (onload, onclick, onerror, etc.)
            if name_lower.startswith("on"):
                continue

            # Drop attributes not explicitly allowed for this tag
            if name_lower not in allowed_attr_names:
                continue

            val_str = "" if val is None else str(val)

            # URL validation for href and src
            if name_lower in ("href", "src") and _is_dangerous_url(val_str):
                continue

            clean_attrs.append((name_lower, val_str))

        # Build attribute string
        attr_parts: list[str] = []
        for name_clean, val_clean in clean_attrs:
            escaped_val = html.escape(val_clean, quote=True)
            attr_parts.append(f'{name_clean}="{escaped_val}"')

        attr_str = f" {' '.join(attr_parts)}" if attr_parts else ""

        if tag_lower in VOID_TAGS:
            self.output.append(f"<{tag_lower}{attr_str} />")
        else:
            self.output.append(f"<{tag_lower}{attr_str}>")
            self._open_tags.append(tag_lower)

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower in STRIP_WITH_CONTENTS:
            if self._strip_content_depth > 0:
                self._strip_content_depth -= 1
            return

        if self._strip_content_depth > 0:
            return

        if tag_lower in VOID_TAGS:
            return

        if tag_lower not in ALLOWED_TAGS:
            return

        # Close tags up to the matching opened tag to maintain well-formedness
        if tag_lower in self._open_tags:
            while self._open_tags:
                opened = self._open_tags.pop()
                self.output.append(f"</{opened}>")
                if opened == tag_lower:
                    break

    def handle_data(self, data: str) -> None:
        if self._strip_content_depth > 0:
            return
        if data:
            self.output.append(html.escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        # If convert_charrefs=True, this is rarely called, but escape if it is
        if self._strip_content_depth > 0:
            return
        self.output.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._strip_content_depth > 0:
            return
        self.output.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        # Drop comments entirely for safety
        pass

    def get_sanitized_html(self) -> str:
        # Close any unclosed tags at EOF to prevent tag leakage
        while self._open_tags:
            opened = self._open_tags.pop()
            self.output.append(f"</{opened}>")
        return "".join(self.output)


def sanitize_html(raw_html: str | None) -> str:
    """
    Sanitize raw HTML by stripping unsafe elements and attributes,
    preserving semantic rich-text elements, and preventing XSS.

    Args:
        raw_html: Untrusted input HTML string, or None.

    Returns:
        Sanitized safe HTML string. Returns "" for None or empty input.
    """
    if not raw_html:
        return ""
    if not isinstance(raw_html, str):
        return ""

    parser = _SanitizingHTMLParser()
    parser.feed(raw_html)
    parser.close()
    return parser.get_sanitized_html()
