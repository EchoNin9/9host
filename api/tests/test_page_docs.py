"""T-31c: block-doc save path (ADR-0003 §1, §3, §4) through the real handler (moto-backed store)."""

import json

from blocks import RenderContext, normalize_own_links, render_doc
from publish_handler import _build_snapshot, _collect_content
from site_compiler import compile_site
from tenant_store import DynamoDBTenantStore
from tests.test_handlers_integration import api, call, create_site, owner, rsa_key, tuser  # noqa: F401


def _doc(*blocks, title=""):
    return {"schema": 1, "root": {"props": {"title": title}}, "content": list(blocks)}


def _rt(html, bid="b1"):
    return {"type": "RichText", "props": {"id": bid, "html": html}}


def _stored(api, site_id, path):
    return DynamoDBTenantStore(api.table).get_content("acme", site_id, "PAGE", path)


def _pages(site_id):
    return f"/api/tenant/sites/{site_id}/pages"


def test_invalid_doc_returns_400_with_path(api):
    site_id = create_site(api)
    tok = owner(api)
    bad = _doc({"type": "Columns", "props": {"id": "c", "count": 2, "col_0": [{"type": "Nope", "props": {}}]}})
    code, body = call("POST", _pages(site_id), tok, body={"path": "about", "doc": bad})
    assert code == 400 and body["path"] == "content[0].props.col_0[0].type" and "unknown block" in body["error"]

    code, body = call("POST", _pages(site_id), tok, body={"path": "about", "doc": {**_doc(), "schema": 9}})
    assert (code, body["path"]) == (400, "schema")
    code, body = call("POST", _pages(site_id), tok, body={"path": "about", "doc": "{not json"})
    assert (code, body["path"]) == (400, "")
    code, body = call("POST", _pages(site_id), tok, body={"path": "about", "doc": "x" * (256 * 1024 + 1)})
    assert code == 400 and "256 KB" in body["error"]
    assert _stored(api, site_id, "about") is None  # nothing written

    assert call("POST", _pages(site_id), tok, body={"path": "about", "title": "A"})[0] == 201
    code, body = call("PUT", f"{_pages(site_id)}/about", tok,
                      body={"doc": _doc({"type": "Hero", "props": {"bogus": 1}})})
    assert (code, body["path"]) == (400, "content[0].props.bogus")
    assert "doc" not in _stored(api, site_id, "about")


def test_doc_stored_sanitized_compact_and_returned_as_object(api):
    site_id = create_site(api)
    xss = '<p>hi<script>alert(1)</script><img src="x" onerror="alert(1)"><a href="javascript:alert(1)">x</a></p>'
    code, body = call("POST", _pages(site_id), owner(api), body={"path": "about", "doc": json.dumps(_doc(_rt(xss)))})
    assert code == 201, body
    stored = _stored(api, site_id, "about")
    assert isinstance(stored["doc"], str) and ": " not in stored["doc"]  # compact JSON string
    for needle in ("<script", "onerror", "javascript:"):
        assert needle not in stored["doc"] and needle not in stored["body"]
    html = json.loads(stored["doc"])["content"][0]["props"]["html"]
    assert html.startswith("<p>hi") and isinstance(body["page"]["doc"], dict)
    assert body["page"]["doc"]["content"][0]["props"]["html"] == html

    code, body = call("GET", f"{_pages(site_id)}/about", owner(api))
    assert code == 200 and body["page"]["doc"] == json.loads(stored["doc"])
    code, body = call("GET", _pages(site_id), owner(api))
    assert code == 200 and "doc" not in body["pages"][0]  # list stays light


def test_dual_write_body_equals_render_doc_and_ignores_foreign_media(api):
    site_id = create_site(api)
    store = DynamoDBTenantStore(api.table)
    store.put_content("acme", site_id, "MEDIA", {"id": "m-own", "s3_key": f"acme/{site_id}/own.png", "caption": "Own"})
    store.put_content("other", "other-site", "MEDIA", {"id": "m-foreign", "s3_key": "other/other-site/x.png"})
    doc = _doc(
        {"type": "Hero", "props": {"id": "h", "heading": "Hi <b>", "image": {"media_id": "m-own"}}},
        {"type": "Image", "props": {"id": "i", "image": {"media_id": "m-foreign"}}},
        _rt("<p>Body</p>", "r"),
    )
    code, body = call("POST", _pages(site_id), owner(api), body={"path": "about", "doc": doc})
    assert code == 201, body
    stored = _stored(api, site_id, "about")
    rctx = RenderContext.build(tenant_slug="acme", site_id=site_id,
                               **_collect_content(api.table, "acme", site_id, published_only=True))
    assert stored["body"] == render_doc(stored["doc"], rctx)
    assert "b-hero" in stored["body"] and "Hi &lt;b&gt;" in stored["body"] and "own.png" in stored["body"]
    assert "x.png" not in stored["body"] and "b-image" not in stored["body"]


def test_title_from_root_props_unless_explicit(api):
    site_id = create_site(api)
    tok = owner(api)
    code, body = call("POST", _pages(site_id), tok, body={"path": "about", "doc": _doc(title="From Doc")})
    assert body["page"]["title"] == "From Doc"
    code, body = call("PUT", f"{_pages(site_id)}/about", tok, body={"title": "Explicit", "doc": _doc(title="Doc")})
    assert body["page"]["title"] == "Explicit"
    code, body = call("PUT", f"{_pages(site_id)}/about", tok, body={"doc": _doc()})
    assert body["page"]["title"] == "Explicit"  # empty root title leaves the title alone


def test_own_host_links_normalized_on_save(api):
    site_id = create_site(api, slug="band")
    tok = owner(api)
    assert call("POST", _pages(site_id), tok, body={"path": "contact", "status": "PUBLISHED"})[0] == 201

    def ll(url):
        return {"label": "x", "link": {"kind": "external", "url": url}}
    doc = _doc({"type": "LinkList", "props": {"id": "l", "items": [
        ll("https://band.echo9.net/contact/"), ll("https://band.echo9.net/"), ll("https://band.echo9.net/missing/"),
        ll("https://example.com/contact/"), ll("https://band.echo9.net/contact/?q=1"),
    ]}})
    code, body = call("POST", _pages(site_id), tok, body={"path": "about", "doc": doc})
    assert code == 201, body
    links = [i["link"] for i in body["page"]["doc"]["content"][0]["props"]["items"]]
    assert [(lk["kind"], lk["path"]) for lk in links] == [
        ("page", "contact"), ("home", ""), ("external", ""), ("external", ""), ("external", "")]
    assert 'href="/contact/"' in _stored(api, site_id, "about")["body"]


def test_normalize_own_links_pure():
    doc = {"content": [{"props": {"col_0": [{"props": {"cta": {"link": {
        "kind": "external", "url": "https://Shop.Example.com/about", "path": "", "new_tab": True}}}}]}}]}
    out = normalize_own_links(doc, {"shop.example.com"}, {"about"})
    assert out["content"][0]["props"]["col_0"][0]["props"]["cta"]["link"] == {
        "kind": "page", "url": "", "path": "about", "new_tab": True}
    assert doc["content"][0]["props"]["col_0"][0]["props"]["cta"]["link"]["kind"] == "external"  # input untouched
    assert normalize_own_links(doc, {"other.com"}, {"about"}) == doc


def test_post_body_sanitized_on_save_page_body_without_doc_kept_raw(api):
    site_id = create_site(api)
    tok = owner(api)
    base = f"/api/tenant/sites/{site_id}/posts"
    code, body = call("POST", base, tok, body={"slug": "p", "body": "<p onclick='x()'>a<script>bad()</script></p>"})
    assert code == 201 and body["post"]["body"] == "<p>a</p>"
    code, body = call("PUT", f"{base}/{body['post']['id']}", tok, body={"body": "<iframe src=x></iframe><b>ok</b>"})
    assert code == 200 and body["post"]["body"] == "<b>ok</b>"

    raw = "<p>legacy<script>kept-at-rest</script></p>"
    assert call("POST", _pages(site_id), tok, body={"path": "old", "body": raw})[0] == 201
    assert _stored(api, site_id, "old")["body"] == raw  # sanitized at render, byte-identical legacy compile


def test_home_path_only_with_doc(api):
    site_id = create_site(api)
    tok = owner(api)
    code, body = call("POST", _pages(site_id), tok, body={"path": "_home", "title": "Home"})
    assert code == 400 and "path" in body["error"]
    assert call("POST", _pages(site_id), tok, body={"path": "admin", "doc": _doc()})[0] == 400  # reserved stays reserved
    code, body = call("POST", _pages(site_id), tok, body={"path": "_home", "doc": _doc(_rt("<p>Welcome</p>"))})
    assert code == 201 and body["page"]["path"] == "_home"
    code, body = call("PUT", f"{_pages(site_id)}/_home", tok, body={"doc": _doc(_rt("<p>Again</p>")), "status": "PUBLISHED"})
    assert code == 200 and "Again" in _stored(api, site_id, "_home")["body"]


def test_site_editor_flag_validation_and_snapshot(api):
    site_id = create_site(api)
    tok = owner(api)
    site_url = f"/api/tenant/sites/{site_id}"
    assert call("GET", site_url, tok)[1]["site"]["editor"] == "richtext"  # default
    code, body = call("PUT", site_url, tok, body={"editor": "wysiwyg"})
    assert code == 400 and "editor" in body["error"]
    assert call("PUT", site_url, tok, body={"editor": 1})[0] == 400
    code, body = call("PATCH", site_url, tok, body={"editor": "blocks"})
    assert code == 200 and body["site"]["editor"] == "blocks"

    doc = _doc({"type": "Hero", "props": {"id": "h", "heading": "Blocky"}})
    assert call("POST", _pages(site_id), tok, body={"path": "about", "doc": doc, "status": "PUBLISHED"})[0] == 201
    store = DynamoDBTenantStore(api.table)
    store.put_content("acme", site_id, "MEDIA", {"id": "m1", "s3_key": f"acme/{site_id}/a.png"})
    snap = _build_snapshot(api.table, "acme", site_id, store.get_site("acme", site_id), {}, "/media/", None,
                           True, "2026-11-14T00:00:00+00:00")
    assert snap.site["editor"] == "blocks"
    assert snap.pages[0]["doc"] == _stored(api, site_id, "about")["doc"] and snap.media[0]["id"] == "m1"
    bundle = compile_site(snap, "live")
    html = bundle.files["about/index.html"].decode()
    assert "b-hero" in html and "Blocky" in html

    assert call("PUT", site_url, tok, body={"editor": "richtext"})[1]["site"]["editor"] == "richtext"


def test_doc_writes_keep_content_permissions(api):
    site_id = create_site(api)
    member = tuser(role="member")
    assert call("POST", _pages(site_id), member, body={"path": "about", "doc": _doc()})[0] == 403
    assert call("POST", _pages(site_id), member, body={"path": "_home", "doc": _doc()})[0] == 403
    assert call("PUT", f"/api/tenant/sites/{site_id}", member, body={"editor": "blocks"})[0] == 403
    assert call("POST", _pages(site_id), body={"path": "about", "doc": _doc()})[0] == 401
