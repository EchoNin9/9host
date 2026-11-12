"""
Tests for api.html_sanitizer.sanitize_html.
Verifies XSS sanitization and semantic HTML preservation.
"""
import pytest
from html_sanitizer import sanitize_html


class TestSanitizeHtmlEdgeCases:
    """Basic edge cases and input validation."""

    def test_none_input_returns_empty_string(self):
        assert sanitize_html(None) == ""

    def test_empty_string_returns_empty_string(self):
        assert sanitize_html("") == ""

    def test_whitespace_string_returns_whitespace(self):
        assert sanitize_html("   ") == "   "

    def test_plain_text_escapes_special_chars(self):
        assert sanitize_html("1 < 2 & 4 > 3") == "1 &lt; 2 &amp; 4 &gt; 3"


class TestSanitizeHtmlAllowedTags:
    """Preservation of allowed semantic rich-text tags and safe attributes."""

    def test_preserves_basic_formatting(self):
        html = "<p>This is <strong>bold</strong>, <em>italic</em>, <u>underline</u>, <s>strike</s>.</p>"
        assert sanitize_html(html) == html

    def test_preserves_headings_and_blockquotes(self):
        html = "<h1>Title</h1><h2>Subtitle</h2><blockquote>A quote</blockquote>"
        assert sanitize_html(html) == html

    def test_preserves_lists(self):
        html = "<ul><li>Item 1</li><li>Item 2</li></ul><ol><li>One</li></ol>"
        assert sanitize_html(html) == html

    def test_preserves_code_and_pre(self):
        html = "<pre><code>const x = 10;</code></pre>"
        assert sanitize_html(html) == html

    def test_preserves_safe_links(self):
        html = '<a href="https://echo9.net" title="Home" target="_blank" rel="noopener noreferrer">Echo9</a>'
        assert sanitize_html(html) == html

    def test_preserves_relative_links(self):
        html = '<a href="/blog/my-post">Read Post</a>'
        assert sanitize_html(html) == html

    def test_preserves_safe_images(self):
        html = '<img src="https://echo9.net/img.png" alt="Logo" title="Echo9" width="100" height="50" />'
        # Self-closing tags can render as <img ... /> or <img ...>
        res = sanitize_html(html)
        assert 'src="https://echo9.net/img.png"' in res
        assert 'alt="Logo"' in res
        assert 'width="100"' in res

    def test_preserves_tables(self):
        html = "<table><thead><tr><th>Header</th></tr></thead><tbody><tr><td>Data</td></tr></tbody></table>"
        assert sanitize_html(html) == html

    def test_preserves_sub_sup_figure_div_span_hr_br(self):
        html = "<div><span>H<sub>2</sub>O and 10<sup>2</sup></span><br /><hr /><figure><figcaption>Caption</figcaption></figure></div>"
        res = sanitize_html(html)
        assert "<sub>2</sub>" in res
        assert "<sup>2</sup>" in res
        assert "<figcaption>Caption</figcaption>" in res

    def test_drops_disallowed_tag_but_keeps_inner_text(self):
        # <marquee> is not allowed, but its text should remain
        html = "<marquee>Scrolling News</marquee>"
        assert sanitize_html(html) == "Scrolling News"

        # Custom / unknown tags keep text
        html2 = "<custom-widget>Custom Text</custom-widget>"
        assert sanitize_html(html2) == "Custom Text"


class TestSanitizeHtmlXSSVectors:
    """Strips or escapes dangerous elements and attributes."""

    def test_strips_script_tag_and_contents(self):
        html = "<p>Hello</p><script>alert('xss');</script><p>World</p>"
        assert sanitize_html(html) == "<p>Hello</p><p>World</p>"

    def test_strips_mixed_case_script_tag(self):
        html = "<ScRiPt type='text/javascript'>alert(1);</sCrIpT>"
        assert sanitize_html(html) == ""

    def test_strips_style_tag_and_contents(self):
        html = "<style>body { background: red; }</style><p>Text</p>"
        assert sanitize_html(html) == "<p>Text</p>"

    def test_strips_iframe_tag_and_contents(self):
        html = "<iframe src='https://malicious.com'>Fallback text</iframe>"
        assert sanitize_html(html) == ""

    def test_strips_object_and_embed_and_contents(self):
        html = "<object data='exploit.swf'>fallback</object><embed src='exploit.swf'>"
        assert sanitize_html(html) == ""

    def test_drops_onerror_event_attribute(self):
        html = '<img src="invalid.jpg" onerror="alert(1)" alt="photo" />'
        res = sanitize_html(html)
        assert "onerror" not in res
        assert "alert" not in res
        assert 'src="invalid.jpg"' in res

    def test_drops_onload_and_other_on_events(self):
        html = '<div onload="evil()" onclick="evil()" onmouseover="evil()"><p onfocus="evil()">Test</p></div>'
        assert sanitize_html(html) == "<div><p>Test</p></div>"

    def test_strips_javascript_href(self):
        html = '<a href="javascript:alert(1)">Click me</a>'
        assert sanitize_html(html) == '<a href="">Click me</a>' or sanitize_html(html) == "<a>Click me</a>"

    def test_strips_vbscript_href(self):
        html = '<a href="vbscript:msgbox(1)">Click me</a>'
        res = sanitize_html(html)
        assert "vbscript" not in res
        assert "msgbox" not in res

    def test_strips_data_text_html_href_and_src(self):
        html = '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">Click</a>'
        res = sanitize_html(html)
        assert "data:text/html" not in res
        assert "alert" not in res

    def test_strips_obfuscated_javascript_url(self):
        # Case insensitive, whitespace, entity obfuscated: jav&#x09;ascript:
        html = '<a href="jav&#x09;ascript:alert(document.cookie)">Click</a>'
        res = sanitize_html(html)
        assert "alert" not in res
        assert "javascript" not in res

        html2 = '<a href="  java\nscript:alert(1)">Click</a>'
        res2 = sanitize_html(html2)
        assert "alert" not in res2

    def test_svg_onload_drops_tag_and_attributes(self):
        html = '<svg onload="alert(1)"><g>test</g></svg>'
        res = sanitize_html(html)
        assert "onload" not in res
        assert "alert" not in res
        assert "test" in res

    def test_unclosed_tags_do_not_leak_or_crash(self):
        html = "<p>Unclosed paragraph<div>Nested <b>bold</b>"
        res = sanitize_html(html)
        assert "Unclosed paragraph" in res
        assert "bold" in res
        # Unclosed tag should not raise exceptions
