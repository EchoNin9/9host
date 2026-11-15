"""T-31b block core: goldens, purity, XSS, validation, links, compile_site integration.

Golden fixtures (shared with the T-31d Vitest parity test): tests/fixtures/blocks/{name}.{mode}.json
holds {"mode": "live"|"draft", "context": {...RenderContext.build kwargs}, "doc": {...}}; the sibling
.html is render_doc(doc, RenderContext.build(**context, base_path="" | "/preview")).
Regenerate after an intentional markup change:  UPDATE_BLOCK_GOLDENS=1 ../.venv/bin/pytest tests/test_blocks.py
"""

import ast
import json
import os
from pathlib import Path

import pytest

from html_sanitizer import _is_dangerous_url
from blocks import (
    BLOCKS, DocValidationError, RenderContext, legacy_doc, link_href, render_doc, rewrite_internal_hrefs,
    validate_doc,
)
from site_compiler import compile_site
from templates import TEMPLATE_RENDERERS
from templates.base_layout import blocks_css
from tests.test_site_compiler import html_files, make_snapshot, parse

FIXTURES = Path(__file__).parent / "fixtures" / "blocks"
GOLDENS = sorted(FIXTURES.glob("*.json"))
BLOCKS_DIR = Path(__file__).parent.parent / "blocks"


def _ctx_for(fixture: dict) -> RenderContext:
    return RenderContext.build(**fixture["context"], base_path="/preview" if fixture["mode"] == "draft" else "")


@pytest.mark.parametrize("path", GOLDENS, ids=[p.stem for p in GOLDENS])
def test_block_goldens(path):
    fixture = json.loads(path.read_text())
    html = render_doc(fixture["doc"], _ctx_for(fixture)) + "\n"
    golden = path.with_suffix(".html")
    if os.environ.get("UPDATE_BLOCK_GOLDENS"):
        golden.write_text(html)
    assert html == golden.read_text()
    if fixture["mode"] == "draft" and not path.name.startswith("richtext_legacy"):  # legacy: unchanged
        for href in parse(html).hrefs:
            assert href.startswith(("/preview/", "https://", "mailto:", "//")), href


def test_goldens_cover_every_block_in_both_modes():
    covered = set()
    for path in GOLDENS:
        def walk(blocks):
            for b in blocks:
                covered.add(b["type"])
                for s in ("col_0", "col_1", "col_2"):
                    walk(b["props"].get(s) or [])
        walk(json.loads(path.read_text())["doc"]["content"])
    assert set(BLOCKS) <= covered
    stems = {p.name.rsplit(".", 2)[0] for p in GOLDENS}
    for stem in stems:
        assert (FIXTURES / f"{stem}.live.json").exists() and (FIXTURES / f"{stem}.draft.json").exists()


def test_goldens_are_valid_docs_except_skip_fixture():
    for path in GOLDENS:
        doc = json.loads(path.read_text())["doc"]
        if path.name.startswith("unknown_block_skipped"):
            with pytest.raises(DocValidationError):
                validate_doc(doc)
        else:
            validate_doc(doc)


# --- purity ------------------------------------------------------------------------------------

FORBIDDEN_MODULES = {"boto3", "botocore", "os", "time", "random", "secrets", "uuid", "socket", "urllib.request"}


def test_blocks_package_is_pure():
    for py in BLOCKS_DIR.glob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                names = []
            for n in names:
                assert n not in FORBIDDEN_MODULES and n.split(".")[0] not in {"boto3", "botocore", "os"}, (py, n)
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"now", "utcnow", "today", "environ", "getenv"}, (py, node.attr)
            if isinstance(node, ast.Name):
                assert node.id not in {"datetime", "date"}, (py, node.id)


# --- XSS corpus --------------------------------------------------------------------------------

XSS = [
    '<script>alert("xss")</script>',
    '"><img src=x onerror=alert(1)>',
    "javascript:alert(1)",
    " JaVaScRiPt:alert(1)",
    "jav&#x09;ascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "'><svg onload=alert(1)>",
    '<iframe src="https://evil.example"></iframe>',
    "</textarea><style>body{display:none}</style>",
    "vbscript:msgbox(1)",
]
CTX = RenderContext.build(
    tenant_slug="acme", site_id="s1", media=[{"id": "m1", "s3_key": "acme/s1/p.jpg", "caption": XSS[1]}],
    pages=[{"path": "about"}], posts=[{"slug": "hello", "title": XSS[0]}], events=[{"title": XSS[1], "event_date": XSS[6]}],
)


def _assert_safe(html: str):
    """No executable markup: text payloads may survive only as escaped text."""
    p = parse(html)
    assert p.scripts == 0 and p.handlers == [], html
    for url in p.hrefs + p.srcs:
        assert not _is_dangerous_url(url) and "evil.example" not in url, url
    for tag in ("<svg", "<style", "<script", "<img src=x", '<iframe src="https://evil'):
        assert tag not in html, (tag, html)


def _doc(*blocks):
    return {"schema": 1, "root": {"props": {}}, "content": list(blocks)}


@pytest.mark.parametrize("payload", XSS)
@pytest.mark.parametrize("base_path", ["", "/preview"])
def test_xss_through_every_text_and_richtext_prop(payload, base_path):
    ctx = RenderContext.build(**{**_CTX_KW, "base_path": base_path})
    link = {"kind": "page", "path": "about"}
    blocks = [
        {"type": "Hero", "props": {"heading": payload, "subheading": payload, "cta": {"label": payload, "link": link}}},
        {"type": "RichText", "props": {"html": payload + '<a href="' + payload + '">x</a>'}},
        {"type": "RichText", "props": {"html": payload, "legacy": True}},
        {"type": "Image", "props": {"image": {"media_id": "m1"}, "alt": payload, "caption": payload}},
        {"type": "CallToAction", "props": {"heading": payload, "text": payload, "button": {"label": payload, "link": link}}},
        {"type": "PostList", "props": {"heading": payload}},
        {"type": "EventList", "props": {"heading": payload}},
        {"type": "LinkList", "props": {"heading": payload, "items": [{"label": payload, "link": link}]}},
        {"type": "Embed", "props": {"provider": "google_maps", "embed_id": "Main St", "title": payload}},
        {"type": "Gallery", "props": {"source": "all"}},
    ]
    html = render_doc(_doc(*blocks), ctx)
    _assert_safe(html)
    assert html.count("<section") >= 4  # blocks rendered (escaped), not skipped
    validate_doc(_doc(*[b for b in blocks if b["type"] != "RichText"]))  # text props are accepted as data


_CTX_KW = dict(
    tenant_slug="acme", site_id="s1", media=[{"id": "m1", "s3_key": "acme/s1/p.jpg", "caption": XSS[1]}],
    pages=[{"path": "about"}], posts=[{"slug": "hello", "title": XSS[0], "excerpt": XSS[6]}],
    events=[{"title": XSS[1], "event_date": XSS[6], "venue": XSS[0]}],
)


@pytest.mark.parametrize("payload", XSS)
def test_xss_in_link_and_embed_props_rejected(payload):
    bad_links = [{"kind": "external", "url": payload}, {"kind": "page", "path": payload},
                 {"kind": "post", "path": payload}]
    for link in bad_links:
        with pytest.raises(DocValidationError):
            validate_doc(_doc({"type": "LinkList", "props": {"items": [{"label": "x", "link": link}]}}))
        # compile-time: invalid block skipped / unresolvable link dropped
        html = render_doc(_doc({"type": "LinkList", "props": {"items": [{"label": "x", "link": link}]}}), CTX)
        _assert_safe(html)
        assert "<a" not in html
        assert link_href(link) == ""
    for provider in ("youtube", "vimeo"):
        with pytest.raises(DocValidationError) as e:
            validate_doc(_doc({"type": "Embed", "props": {"provider": provider, "embed_id": payload}}))
        assert e.value.path == "content[0].props.embed_id"
        assert render_doc(_doc({"type": "Embed", "props": {"provider": provider, "embed_id": payload}}), CTX) == ""


def test_richtext_sanitized_on_validate_with_unchanged_allowlist():
    doc = validate_doc(_doc({"type": "RichText", "props": {"id": "r", "html": '<p class="x" style="y">ok</p><script>1</script><iframe></iframe>'}}))
    assert doc["content"][0]["props"]["html"] == "<p>ok</p>"


def test_text_props_strip_control_chars():
    doc = validate_doc(_doc({"type": "Hero", "props": {"heading": "a\x00b\x1fc\nd"}}))
    assert doc["content"][0]["props"]["heading"] == "abc\nd"


def test_new_tab_links_get_noopener():
    html = render_doc(_doc({"type": "LinkList", "props": {"items": [
        {"label": "x", "link": {"kind": "external", "url": "https://e.com/", "new_tab": True}}]}}), CTX)
    assert 'target="_blank" rel="noopener noreferrer"' in html


def test_embed_is_fixed_template_for_allowlisted_providers_only():
    with pytest.raises(DocValidationError) as e:
        validate_doc(_doc({"type": "Embed", "props": {"provider": "evil", "embed_id": "x"}}))
    assert e.value.path == "content[0].props.provider"
    with pytest.raises(DocValidationError):
        validate_doc(_doc({"type": "Embed", "props": {"provider": "youtube", "embed_id": "dQw4w9WgXcQ", "url": "https://e"}}))
    html = render_doc(_doc({"type": "Embed", "props": {"provider": "youtube", "embed_id": "dQw4w9WgXcQ"}}), CTX)
    assert 'src="https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"' in html and "sandbox=" in html
    maps = render_doc(_doc({"type": "Embed", "props": {"provider": "google_maps", "embed_id": "a&b=c#d"}}), CTX)
    assert "q=a%26b%3Dc%23d&amp;output=embed" in maps


# --- validation ------------------------------------------------------------------------------

def _err(doc) -> DocValidationError:
    with pytest.raises(DocValidationError) as e:
        validate_doc(doc)
    assert isinstance(e.value, ValueError)
    return e.value


def test_validation_error_paths():
    assert _err({"schema": 2, "content": []}).path == "schema"
    assert _err({"schema": 1, "content": [], "extra": 1}).path == "extra"
    assert _err(_doc({"type": "Marquee", "props": {}})).path == "content[0].type"
    assert _err(_doc({"type": "Divider", "props": {}}, {"type": "Hero", "props": {"bogus": 1}})).path == "content[1].props.bogus"
    assert _err(_doc({"type": "Hero", "props": {"align": "right"}})).path == "content[0].props.align"
    assert _err(_doc({"type": "Hero", "props": {"heading": 5}})).path == "content[0].props.heading"
    assert _err(_doc({"type": "PostList", "props": {"count": 99}})).path == "content[0].props.count"
    assert _err(_doc({"type": "Hero", "props": {"cta": {"label": "x", "link": {"kind": "page", "path": "../x"}}}})).path == (
        "content[0].props.cta.link.path")
    cols = {"type": "Columns", "props": {"count": 2, "col_0": [{"type": "Hero", "props": {}}],
                                         "col_1": [{"type": "Nope", "props": {}}]}}
    assert _err(_doc({"type": "Divider", "props": {}}, cols)).path == "content[1].props.col_1[0].type"
    assert _err(_doc({"type": "Hero"}, "x")).path == "content[1]"
    assert _err("{not json").path == ""
    assert _err({"schema": 1, "root": {"props": {"color": "red"}}, "content": []}).path == "root.props.color"


def _nest(depth):
    block = {"type": "Divider", "props": {}}
    for _ in range(depth - 1):
        block = {"type": "Columns", "props": {"count": 2, "col_0": [block]}}
    return _doc(block)


def test_depth_cap():
    validate_doc(_nest(3))
    err = _err(_nest(4))
    assert err.path == "content[0].props.col_0[0].props.col_0[0].props.col_0[0]"
    assert "hr" not in render_doc(_nest(4), CTX) and "b-columns" in render_doc(_nest(4), CTX)
    assert '<hr class="b-divider">' in render_doc(_nest(3), CTX)


def test_block_count_cap():
    validate_doc(_doc(*[{"type": "Divider", "props": {}}] * 200))
    assert _err(_doc(*[{"type": "Divider", "props": {}}] * 201)).path == "content[200]"
    assert render_doc(_doc(*[{"type": "Divider", "props": {}}] * 250), CTX).count("<hr") == 200


def test_size_cap():
    big = "x" * (256 * 1024)
    doc = _doc({"type": "RichText", "props": {"html": big}})
    assert "256 KB" in str(_err(doc))
    assert "256 KB" in str(_err(json.dumps(doc)))
    assert render_doc(json.dumps(doc), CTX) == ""


def test_validate_doc_accepts_json_string_and_normalizes():
    doc = validate_doc(json.dumps(_doc({"type": "Spacer", "props": {"id": "s"}})))
    assert doc == {"schema": 1, "root": {"props": {"title": "", "meta_description": ""}},
                   "content": [{"type": "Spacer", "props": {"id": "s", "size": "md"}}]}


# --- media / links -----------------------------------------------------------------------------

def test_foreign_media_id_renders_nothing():
    for block in ({"type": "Image", "props": {"image": {"media_id": "other-tenant"}}},
                  {"type": "Gallery", "props": {"items": [{"media_id": "other-tenant"}]}}):
        assert render_doc(_doc(block), CTX) == ""
    hero = render_doc(_doc({"type": "Hero", "props": {"heading": "h", "image": {"media_id": "nope"}}}), CTX)
    assert "<img" not in hero
    img = render_doc(_doc({"type": "Image", "props": {"image": {"media_id": "m1"}}}), CTX)
    assert 'src="/media/acme/s1/p.jpg"' in img


def test_link_href_live_vs_draft():
    cases = [
        ({"kind": "home"}, "/", "/preview/"),
        ({"kind": "page", "path": "about"}, "/about/", "/preview/about/"),
        ({"kind": "post", "path": "hello"}, "/posts/hello/", "/preview/posts/hello/"),
        ({"kind": "blog"}, "/blog/", "/preview/blog/"),
        ({"kind": "events"}, "/events/", "/preview/events/"),
        ({"kind": "gallery"}, "/gallery/", "/preview/gallery/"),
        ({"kind": "external", "url": "https://e.com/x"}, "https://e.com/x", "https://e.com/x"),
        ({"kind": "external", "url": "mailto:a@b.c"}, "mailto:a@b.c", "mailto:a@b.c"),
        ({"kind": "external", "url": "ftp://e.com"}, "", ""),
        ({"kind": "external", "url": "//evil.com"}, "", ""),
        ({"kind": "page", "path": "../etc"}, "", ""),
        ({"kind": "bogus"}, "", ""),
        (None, "", ""),
    ]
    for link, live, draft in cases:
        assert link_href(link, "") == live, link
        assert link_href(link, "/preview") == draft, link


def test_rewrite_internal_hrefs():
    html = '<a href="/about/">a</a><a href="//cdn.x/y">b</a><a href="https://e.com/">c</a><a href="#t">d</a><img src="/media/x.png" />'
    assert rewrite_internal_hrefs(html, "") == html
    out = rewrite_internal_hrefs(html, "/preview")
    assert '<a href="/preview/about/">' in out
    assert 'href="//cdn.x/y"' in out and 'href="https://e.com/"' in out and 'href="#t"' in out
    assert 'src="/media/x.png"' in out  # media srcs are never prefixed
    assert rewrite_internal_hrefs('<a href="/">h</a>', "/preview/") == '<a href="/preview/">h</a>'


def test_legacy_doc_renders_like_render_page_body():
    ctx = RenderContext.build(tenant_slug="acme", site_id="s1", base_path="/preview")
    body = '<p><a href="/about/">a</a></p><img src="https://b.s3.amazonaws.com/acme/s1/p.png">'
    out = render_doc(legacy_doc(body), ctx)
    assert out == '<div class="content"><p><a href="/about/">a</a></p><img src="/media/acme/s1/p.png" /></div>'
    assert render_doc(legacy_doc(None), ctx) == '<div class="content"></div>'


# --- compile_site integration ------------------------------------------------------------------

HOME = {"schema": 1, "root": {"props": {"meta_description": "Home desc"}}, "content": [
    {"type": "Hero", "props": {"heading": "Welcome home", "cta": {"label": "About", "link": {"kind": "page", "path": "about"}}}}]}
ABOUT = {"schema": 1, "root": {"props": {}}, "content": [
    {"type": "RichText", "props": {"html": '<p>Go <a href="/blog/">blog</a></p>'}},
    {"type": "Image", "props": {"image": {"media_id": "m1"}}}]}


def _blocks_snapshot(slug="business-generic", editor="blocks"):
    return make_snapshot(
        slug,
        site={"name": "Acme", "slug": "acme-band", "editor": editor, "branding": {}},
        pages=[{"path": "about", "title": "About", "body": "<p>legacy body</p>", "doc": json.dumps(ABOUT)},
               {"path": "_home", "title": "Home", "body": "", "doc": json.dumps(HOME)},
               {"path": "plain", "title": "Plain", "body": '<p>old <a href="/about/">x</a></p>'}],
        media=[{"id": "m1", "s3_key": "acme/s1/photo.jpg", "caption": "Cap"}],
    )


@pytest.mark.parametrize("slug", sorted(TEMPLATE_RENDERERS))
def test_blocks_site_live(slug):
    bundle = compile_site(_blocks_snapshot(slug))
    files = html_files(bundle)
    assert "_home/index.html" not in files
    assert "/_home/" not in files["index.html"] and "/_home/" not in bundle.files["sitemap.xml"].decode()
    assert all("_home" not in html for html in files.values())  # never a nav entry or page
    index = files["index.html"]
    assert '<section class="b-hero b-hero--center">' in index and 'href="/about/"' in index
    assert 'class="hero"' not in index and "page-nav" not in index  # render_index replaced
    assert '<meta name="description" content="Home desc">' in index
    about = files["about/index.html"]
    assert '<h2 class="page-title">About</h2>' in about
    assert '<div class="b-richtext content"><p>Go <a href="/blog/">blog</a></p></div>' in about
    assert 'src="/media/acme/s1/photo.jpg"' in about and "legacy body" not in about
    assert '<div class="content"><p>old <a href="/about/">x</a></p></div>' in files["plain/index.html"]
    css = bundle.files["style.css"].decode()
    assert css.endswith(blocks_css()) and ".b-hero" in css


def test_blocks_site_draft_rewrites_doc_hrefs_only():
    files = html_files(compile_site(_blocks_snapshot(), mode="draft"))
    about = files["about/index.html"]
    assert 'href="/preview/blog/"' in about and ".b-hero" in about  # CSS inlined incl. blocks_css
    assert 'href="/preview/about/"' in files["index.html"]
    # legacy pages keep today's draft output (internal body links not rewritten)
    assert '<p>old <a href="/about/">x</a></p>' in files["plain/index.html"]


def test_blocks_site_without_home_doc_keeps_render_index():
    snap = _blocks_snapshot()
    pages = [p for p in snap.pages if p["path"] != "_home"] + [{"path": "_home", "title": "H", "body": "<p>x</p>"}]
    files = html_files(compile_site(make_snapshot(site=snap.site, pages=pages, media=snap.media)))
    assert 'class="hero"' in files["index.html"] and "_home" not in files["index.html"]


def test_richtext_site_ignores_doc_and_blocks_css():
    bundle = compile_site(_blocks_snapshot(editor="richtext"))
    files = html_files(bundle)
    assert "legacy body" in files["about/index.html"] and "b-richtext" not in files["about/index.html"]
    assert ".b-hero" not in bundle.files["style.css"].decode()
    assert 'class="hero"' in files["index.html"]


def test_blocks_compile_is_deterministic_and_xss_free():
    a, b = compile_site(_blocks_snapshot()), compile_site(_blocks_snapshot())
    assert a == b
    evil = {"schema": 1, "content": [{"type": "RichText", "props": {"html": XSS[0] + XSS[1]}},
                                     {"type": "Hero", "props": {"heading": XSS[0]}}]}
    snap = make_snapshot(site={"name": "A", "slug": "a", "editor": "blocks"},
                         pages=[{"path": "about", "title": "t", "doc": json.dumps(evil)},
                                {"path": "bad", "title": "b", "doc": "{not json"}])
    for mode in ("live", "draft"):
        for path, html in html_files(compile_site(snap, mode=mode)).items():
            p = parse(html)
            assert p.scripts == (0 if mode == "live" else 1) and p.handlers == [], path
