"""T-04: pure SiteCompiler (root-relative links, /preview drafts, stored-XSS sanitization)
and SiteStoragePort (in-memory + moto S3) round-trips."""

import json
import re
from html.parser import HTMLParser

import boto3
import pytest
from moto import mock_aws

from site_compiler import CompiledSiteBundle, SiteSnapshot, compile_site
from site_storage import InMemorySiteStorage, S3SiteStorageAdapter
from templates import TEMPLATE_RENDERERS

TEMPLATES = sorted(TEMPLATE_RENDERERS)
XSS_BODY = (
    '<p>Hello <strong>world</strong></p>'
    '<script>alert("xss-script")</script>'
    '<img src="x.png" onerror="alert(\'xss-onerror\')">'
    '<a href="javascript:alert(\'xss-js\')">click</a>'
    '<a href=" JaVaScRiPt:alert(1)">obfuscated</a>'
    '<iframe src="https://evil.example"></iframe>'
    '<div onclick="steal()">div</div>'
)


def make_snapshot(template_slug="business-generic", body=XSS_BODY, **overrides) -> SiteSnapshot:
    data = dict(
        tenant_slug="acme",
        site_id="s1",
        site={"name": "Acme <Band>", "slug": "acme-band", "branding": {"logo_s3_key": "acme/s1/logo.png"}},
        template={"slug": template_slug},
        pages=[{"path": "about", "title": "About <us>", "body": body}],
        posts=[{"slug": "hello", "title": "Hello", "body": body, "excerpt": "", "featured_image_s3_key": ""}],
        events=[{"title": "Gig <live>", "event_date": "2026-12-01", "venue": "Hall"}],
        media=[{"s3_key": "acme/s1/photo.jpg", "caption": 'Cap"tion'}],
        generated_at="2026-11-11T00:00:00+00:00",
        media_base="/media/",
        base_domain="echo9.net",
    )
    data.update(overrides)
    return SiteSnapshot(**data)


def html_files(bundle: CompiledSiteBundle) -> dict[str, str]:
    return {p: b.decode("utf-8") for p, b in bundle.files.items() if p.endswith(".html")}


class _LinkAndScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs, self.srcs, self.scripts, self.handlers = [], [], 0, []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.scripts += 1
        for name, value in attrs:
            if name == "href":
                self.hrefs.append(value or "")
            if name == "src":
                self.srcs.append(value or "")
            if name.startswith("on"):
                self.handlers.append(name)


def parse(html: str) -> _LinkAndScriptParser:
    p = _LinkAndScriptParser()
    p.feed(html)
    p.close()
    return p


EXPECTED_FILES = {
    "index.html", "about/index.html", "blog/index.html", "posts/hello/index.html",
    "events/index.html", "gallery/index.html", "404.html",
}


@pytest.mark.parametrize("slug", TEMPLATES)
def test_all_templates_compile_valid_html(slug):
    bundle = compile_site(make_snapshot(slug))
    assert EXPECTED_FILES | {"style.css", "sitemap.xml", "robots.txt"} == set(bundle.files)
    for path, html in html_files(bundle).items():
        assert html.startswith("<!DOCTYPE html>"), path
        assert html.rstrip().endswith("</html>"), path
        for tag in ("html", "head", "body", "main", "header", "footer"):
            assert len(re.findall(rf"<{tag}[\s>]", html)) == html.count(f"</{tag}>") == 1, (path, tag)
        assert "&copy; 2026 Acme &lt;Band&gt;" in html
    assert b"--" in bundle.files["style.css"] or len(bundle.files["style.css"]) > 100


@pytest.mark.parametrize("slug", TEMPLATES)
def test_live_mode_links_are_root_relative(slug):
    bundle = compile_site(make_snapshot(slug), mode="live")
    for path, html in html_files(bundle).items():
        assert "/site/" not in html, path
        assert "/preview" not in html, path
        parsed = parse(html)
        internal = [h for h in parsed.hrefs if not h.startswith(("http://", "https://", "mailto:"))]
        assert internal, path
        for href in internal:
            assert href.startswith("/"), (path, href)
            assert not href.startswith("//"), (path, href)
    index = html_files(bundle)["index.html"]
    for href in ('href="/about/"', 'href="/blog/"', 'href="/events/"', 'href="/gallery/"', 'href="/style.css"'):
        assert href in index
    assert 'href="/posts/hello/"' in html_files(bundle)["blog/index.html"]
    assert 'href="/"' in html_files(bundle)["404.html"]
    sitemap = bundle.files["sitemap.xml"].decode()
    assert "<loc>https://acme-band.echo9.net/posts/hello/</loc>" in sitemap


@pytest.mark.parametrize("slug", TEMPLATES)
def test_draft_mode_uses_preview_prefix(slug):
    bundle = compile_site(make_snapshot(slug), mode="draft")
    assert set(bundle.files) == EXPECTED_FILES  # no style.css/sitemap/robots in drafts
    for path, html in html_files(bundle).items():
        assert "/site/" not in html, path
        assert "<style>" in html and 'rel="stylesheet"' not in html, path  # CSS inlined
        for href in parse(html).hrefs:
            assert href.startswith("/preview/"), (path, href)
    index = html_files(bundle)["index.html"]
    assert 'href="/preview/blog/"' in index and 'href="/preview/about/"' in index


@pytest.mark.parametrize("mode", ["live", "draft"])
@pytest.mark.parametrize("slug", TEMPLATES)
def test_user_content_xss_never_survives(slug, mode):
    bundle = compile_site(make_snapshot(slug), mode=mode)
    for path, html in html_files(bundle).items():
        for marker in ("xss-script", "xss-onerror", "xss-js", "steal()", "evil.example", "<iframe"):
            assert marker not in html, (path, marker)
        assert not re.search(r"javascript:", html, re.IGNORECASE), path
        parsed = parse(html)
        assert parsed.handlers == [], path
        # live: zero <script>; draft: only the platform token-propagation script
        assert parsed.scripts == (0 if mode == "live" else 1), path
    page = html_files(bundle)["about/index.html"]
    assert "<p>Hello <strong>world</strong></p>" in page  # semantic tags preserved
    assert "About &lt;us&gt;" in page  # plain text escaped


def test_plain_text_fields_escaped():
    snap = make_snapshot(pages=[{"path": 'x"><script>alert(1)</script>', "title": "<b>t</b>", "body": ""}])
    for html in html_files(compile_site(snap)).values():
        assert "<script>" not in html
        assert "<b>t</b>" not in html


def test_compile_is_deterministic():
    a = compile_site(make_snapshot("musician-band"))
    b = compile_site(make_snapshot("musician-band"))
    assert a == b
    assert a.manifest == b.manifest


def test_content_types_cover_every_file():
    for mode in ("live", "draft"):
        bundle = compile_site(make_snapshot(), mode=mode)
        assert set(bundle.content_types) == set(bundle.files)
        assert {m["path"] for m in bundle.manifest["files"]} == set(bundle.files)
    live = compile_site(make_snapshot())
    assert live.content_types["index.html"] == "text/html; charset=utf-8"
    assert live.content_types["style.css"] == "text/css; charset=utf-8"
    assert live.content_types["sitemap.xml"] == "application/xml; charset=utf-8"
    assert live.content_types["robots.txt"] == "text/plain; charset=utf-8"


def test_forked_template_and_unknown_fallback():
    forked = compile_site(make_snapshot(template={"slug": "my-fork", "forked_from": "personal-tech"}))
    direct = compile_site(make_snapshot("personal-tech"))
    assert forked.files["style.css"] == direct.files["style.css"]
    unknown = compile_site(make_snapshot("does-not-exist"))
    assert unknown.files["style.css"] == compile_site(make_snapshot("business-generic")).files["style.css"]


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        compile_site(make_snapshot(), mode="preview")


# --- SiteStoragePort ---------------------------------------------------------

def test_in_memory_publish_draft_rollback_round_trip():
    storage = InMemorySiteStorage()
    v1 = compile_site(make_snapshot(site={"name": "One", "slug": "one"}))
    v2 = compile_site(make_snapshot(site={"name": "Two", "slug": "one"}))

    r1 = storage.publish("acme", "s1", v1, published_at="t1")
    assert r1 == {"version": 1, "published_at": "t1", "files_count": len(v1.files), "is_default": True}
    assert storage.read("acme/default.json") is not None
    r2 = storage.publish("acme", "s1", v2, published_at="t2")
    assert r2["version"] == 2 and r2["is_default"] is False

    cur = "acme/s1/published/current/index.html"
    assert "Two" in storage.read(cur)
    assert json.loads(storage.read("acme/s1/published/current.json"))["version"] == 2
    manifest = json.loads(storage.read("acme/s1/published/v2/manifest.json"))
    assert manifest["version"] == 2 and {f["path"] for f in manifest["files"]} == set(v2.files)
    body, ctype, cache = storage.objects["acme/s1/published/v2/style.css"]
    assert ctype.startswith("text/css") and "immutable" in cache

    rb = storage.rollback("acme", "s1", 1, now="t3")
    assert rb == {"version": 1, "rolled_back_at": "t3"}
    assert "One" in storage.read(cur)
    assert json.loads(storage.read("acme/s1/published/current.json"))["version"] == 1
    assert storage.rollback("acme", "s1", 99) is None

    # After rolling back, the next publish must not overwrite existing v2.
    assert storage.publish("acme", "s1", v2, published_at="t4")["version"] == 3

    draft = compile_site(make_snapshot(), mode="draft")
    assert storage.publish_draft("acme", "s1", draft) == {"files_count": len(draft.files)}
    _, _, cache = storage.objects["acme/s1/draft/index.html"]
    assert "no-store" in cache


def test_s3_adapter_round_trip_with_moto():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="9host-sites")
        storage = S3SiteStorageAdapter(s3)
        bundle = compile_site(make_snapshot())
        assert storage.publish("acme", "s1", bundle, published_at="t1")["version"] == 1
        assert storage.publish("acme", "s1", bundle, published_at="t2")["version"] == 2
        obj = s3.get_object(Bucket="9host-sites", Key="acme/s1/published/current/index.html")
        assert obj["ContentType"] == "text/html; charset=utf-8"
        assert obj["Body"].read() == bundle.files["index.html"]
        assert storage.rollback("acme", "s1", 1)["version"] == 1
        assert storage.rollback("acme", "s1", 7) is None
        cur = json.loads(s3.get_object(Bucket="9host-sites", Key="acme/s1/published/current.json")["Body"].read())
        assert cur["version"] == 1


# --- publish_handler through the storage port --------------------------------

def test_publish_handler_uses_compiler_and_storage_port(dynamodb_table):
    import publish_handler
    from tenant_store import DynamoDBTenantStore

    table = dynamodb_table
    site_item = {"pk": "TENANT#acme", "sk": "SITE#s1", "name": "Acme", "slug": "acme", "template_id": "musician-band"}
    table.put_item(Item=site_item)
    store = DynamoDBTenantStore(table)
    store.put_content("acme", "s1", "PAGE", {"path": "about", "title": "About", "body": XSS_BODY, "status": "PUBLISHED"})
    store.put_content("acme", "s1", "PAGE", {"path": "secret", "title": "Secret", "body": "x", "status": "DRAFT"})
    store.put_content("acme", "s1", "POST", {"slug": "p1", "title": "P1", "body": "<p>b</p>", "status": "PUBLISHED"})

    storage = InMemorySiteStorage()
    features = {"updates_blog": True, "events_shows": True, "branding": True}
    result = publish_handler._publish_site(
        table, None, "acme", "s1", site_item, {"slug": "musician-band"}, "/media/", features, storage=storage,
    )
    assert result["version"] == 1 and result["is_default"] is True
    keys = set(storage.objects)
    assert "acme/s1/published/current/about/index.html" in keys
    assert "acme/s1/published/current/posts/p1/index.html" in keys
    assert not any("secret" in k for k in keys)  # drafts excluded from live publish
    about = storage.read("acme/s1/published/current/about/index.html")
    assert "xss-script" not in about and 'href="/blog/"' in about and "/site/" not in about
    assert storage.host_mappings == [("acme", "s1", ["acme.echo9.net"])]
    row = table.get_item(Key={"pk": "TENANT#acme", "sk": "SITE#s1"})["Item"]
    assert row["status"] == "published" and int(row["published_version"]) == 1

    # Feature gating: no blog module -> no blog pages. Draft includes DRAFT content under /preview.
    draft = publish_handler._draft_publish_site(
        table, None, "acme", "s1", site_item, {"slug": "musician-band"}, "/media/",
        {"updates_blog": False, "events_shows": True, "branding": True}, storage=storage,
    )
    assert draft["files_count"] == len([k for k in storage.objects if k.startswith("acme/s1/draft/")])
    assert "acme/s1/draft/secret/index.html" in storage.objects
    assert "acme/s1/draft/blog/index.html" not in storage.objects

    rb = publish_handler._rollback_site(table, None, "acme", "s1", 1, storage=storage)
    assert rb["version"] == 1
    assert publish_handler._rollback_site(table, None, "acme", "s1", 5, storage=storage) is None
