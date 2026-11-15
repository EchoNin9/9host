"""T-32a: platform template data + versioning (ADR-0003 §5).

Store-level versioning/immutability, token/preset validation, seed idempotency, the superadmin
admin API (versions, publish, deprecate, preview, bulk upgrade), site pinning / "update to vN",
preset seeding on apply, and token emission only for block-editor sites.
"""

import json
import os
import sys

import pytest

from blocks import DocValidationError
from publish_handler import _compile_inputs
from site_compiler import compile_site
from template_schema import validate_allowed_blocks, validate_page_presets, validate_tokens, validate_version
from templates.base_layout import template_tokens_css
from tenant_store import DynamoDBTenantStore, InMemoryTenantStore
from tests.test_handlers_integration import api, call, owner, rsa_key, superadmin, tuser  # noqa: F401
from tests.test_site_compiler import make_snapshot

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import seed_templates  # noqa: E402

DOC = {"schema": 1, "root": {"props": {"title": "About us"}},
       "content": [{"type": "RichText", "props": {"html": "<p>Hi<script>x</script></p>"}}]}


def _head(store, slug="tpl", **extra):
    return store.put_template_head(slug, {"name": slug, "tier_required": "FREE", "base_renderer": "personal-tech",
                                          "latest_version": 0, "published_version": 0, **extra})


# ---------------------------------------------------------------------------
# TenantStore
# ---------------------------------------------------------------------------


@pytest.fixture(params=["memory", "dynamodb"])
def store(request, dynamodb_table):
    return InMemoryTenantStore() if request.param == "memory" else DynamoDBTenantStore(dynamodb_table)


def test_versions_append_and_are_immutable(store):
    _head(store)
    assert store.put_template_version("tpl", {"tokens": {"primary": "#111"}}) == 1
    assert store.put_template_version("tpl", {"tokens": {"primary": "#222"}}) == 2
    assert store.get_template("tpl")["latest_version"] == 2
    with pytest.raises(KeyError):  # explicit existing n: conditional put refuses
        store.put_template_version("tpl", {"tokens": {"primary": "#999"}}, n=1)
    assert store.get_template_version("tpl", 1)["tokens"] == {"primary": "#111"}
    assert [v["version"] for v in store.list_template_versions("tpl")] == [1, 2]
    with pytest.raises(KeyError):
        store.put_template_version("missing", {})


def test_list_templates_returns_heads_only(store):
    _head(store, "a")
    _head(store, "b")
    store.put_template_version("a", {})
    store.put_template_version("a", {})
    assert [t["slug"] for t in store.list_templates()] == ["a", "b"]
    assert [v["version"] for v in store.list_template_versions("a")] == [1, 2]
    assert store.list_template_versions("b") == []


def test_head_create_only_conflicts(store):
    _head(store)
    with pytest.raises(KeyError):
        store.put_template_head("tpl", {"name": "x"}, create_only=True)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_token_validation():
    good = {"primary": "#ff0000", "secondary": "#0f0", "bg": "#ffffff", "text": "#111111",
            "heading_font": "Georgia, 'Times New Roman'", "body_font": "Inter", "radius": "8px", "spacing": "1.5rem"}
    assert validate_tokens(good) == good
    for bad in ({"primary": "red"}, {"primary": "#fff;}body{x:y"}, {"radius": "100px"}, {"radius": "8em"},
                {"spacing": "1rem;"}, {"body_font": "x</style>"}, {"nope": "#fff"}, {"primary": 3}):
        with pytest.raises(DocValidationError):
            validate_tokens(bad)
    css = template_tokens_css({"primary": "#ff0000", "radius": "8px", "bg": "url(x)"})
    assert "--template-primary: #ff0000;" in css and "--template-radius: 8px;" in css and "url(" not in css


def test_preset_and_allowed_blocks_validation():
    presets = validate_page_presets({"_home": DOC, "about": DOC})
    assert "<script" not in json.dumps(presets)  # richtext sanitized like a page save
    for path in ("admin", "blog", "About", "a/b", "_other"):
        with pytest.raises(DocValidationError):
            validate_page_presets({path: DOC})
    with pytest.raises(DocValidationError) as e:
        validate_page_presets({"about": {"schema": 1, "content": [{"type": "Nope", "props": {}}]}})
    assert e.value.path.startswith("page_presets.about.content[0]")
    assert validate_allowed_blocks(["Hero", "RichText"]) == {"Hero": True, "RichText": True}
    assert validate_allowed_blocks({"Columns": "pro", "Hero": False}) == {"Columns": "PRO"}
    with pytest.raises(DocValidationError):
        validate_allowed_blocks({"Script": True})
    with pytest.raises(DocValidationError):
        validate_version({"header": {"nav_style": "fancy"}})
    v = validate_version({"footer": {"text": "Hi", "links": [{"label": "X", "link": {"kind": "page", "path": "about"}}]}})
    assert v["header"] == {"show_logo": True, "nav_style": "default"} and v["footer"]["text"] == "Hi"
    with pytest.raises(DocValidationError):
        validate_version({"footer": {"links": [{"label": "X", "link": {"kind": "external", "url": "javascript:x"}}]}})


# ---------------------------------------------------------------------------
# Seed migration
# ---------------------------------------------------------------------------


class CountingStore(InMemoryTenantStore):
    def __init__(self):
        super().__init__()
        self.writes = []

    def _put(self, item):
        self.writes.append(item["sk"])
        super()._put(item)

    def _set_attrs_if_exists(self, pk, sk, attrs):
        self.writes.append(sk)
        super()._set_attrs_if_exists(pk, sk, attrs)


def test_seed_migrates_legacy_heads_once():
    store = CountingStore()
    for t in seed_templates.TEMPLATES:  # prod today: legacy heads, possibly superadmin-edited
        store._put({"pk": "TENANT#_platform", "sk": f"TEMPLATE#{t['slug']}", "slug": t["slug"],
                    "name": "Edited", "tier_required": t["tier_required"], "components": t["components"]})
    store.writes.clear()

    assert seed_templates.seed(store, dry_run=True) == {"heads_created": 0, "heads_updated": 5, "versions_created": 5}
    assert store.writes == []

    counts = seed_templates.seed(store)
    assert counts == {"heads_created": 0, "heads_updated": 5, "versions_created": 5}
    assert len(store.writes) == 10
    assert all(pk == "TENANT#_platform" and sk.startswith("TEMPLATE#") for pk, sk in store.items)
    head = store.get_template("personal-tech")
    assert head["name"] == "Edited"  # never overwritten
    assert (head["base_renderer"], head["latest_version"], head["published_version"]) == ("personal-tech", 1, 1)
    v1 = store.get_template_version("personal-tech", 1)
    presets = {p: json.loads(d) for p, d in v1["page_presets"].items()}
    assert sorted(presets) == ["_home", "about", "contact", "projects"]  # "blog" is compiler-generated
    assert len(presets["_home"]["content"]) == 3  # hero, projects-preview, cta
    validate_page_presets(presets)

    store.writes.clear()
    assert seed_templates.seed(store) == {"heads_created": 0, "heads_updated": 0, "versions_created": 0}
    assert store.writes == []


def test_seed_creates_missing_templates_and_is_idempotent_on_dynamodb(dynamodb_table):
    store = DynamoDBTenantStore(dynamodb_table)
    assert seed_templates.seed(store) == {"heads_created": 5, "heads_updated": 0, "versions_created": 5}
    before = sorted(json.dumps(i, default=str, sort_keys=True) for i in dynamodb_table.scan()["Items"])
    assert len(before) == 10
    assert seed_templates.seed(store) == {"heads_created": 0, "heads_updated": 0, "versions_created": 0}
    assert sorted(json.dumps(i, default=str, sort_keys=True) for i in dynamodb_table.scan()["Items"]) == before


# ---------------------------------------------------------------------------
# Compile: tokens only for block-editor sites
# ---------------------------------------------------------------------------

TOKENS = {"primary": "#ff0000", "body_font": "Georgia"}


def test_tokens_emitted_only_for_blocks_sites():
    legacy = compile_site(make_snapshot(template={"slug": "personal-tech", "tokens": TOKENS}))
    assert legacy.files == compile_site(make_snapshot(template={"slug": "personal-tech"})).files
    assert b"--template-primary: #ff0000" not in legacy.files["style.css"]
    blocks_site = {"name": "A", "slug": "a", "editor": "blocks", "branding": {}}
    css = compile_site(make_snapshot(site=blocks_site, template={"slug": "personal-tech", "tokens": TOKENS}))
    assert b"--template-primary: #ff0000;" in css.files["style.css"]
    assert b"var(--brand-font, var(--template-body-font))" in css.files["style.css"]


def test_base_renderer_selects_renderer():
    a = compile_site(make_snapshot(template={"slug": "custom", "base_renderer": "musician-band"}))
    b = compile_site(make_snapshot(template={"slug": "musician-band"}))
    assert a.files == b.files


def test_publish_loads_pinned_version_tokens():
    store = InMemoryTenantStore()
    store.put_tenant("acme", {"tier": "PRO"})
    _head(store, published_version=2)
    store.put_template_version("tpl", {"tokens": {"primary": "#111111"}})
    store.put_template_version("tpl", {"tokens": {"primary": "#222222"}})
    site = {"template_id": "tpl", "editor": "blocks", "template_version": 1}
    assert _compile_inputs(store, "acme", site)[0]["tokens"] == {"primary": "#111111"}
    assert _compile_inputs(store, "acme", {**site, "template_version": None})[0]["tokens"] == {"primary": "#111111"}
    assert "tokens" not in _compile_inputs(store, "acme", {**site, "editor": "richtext"})[0]


# ---------------------------------------------------------------------------
# Admin API + sites (moto, full handler)
# ---------------------------------------------------------------------------

T = "/api/admin/templates"


def sa(api, method, path, body=None):
    return call(method, path, superadmin(api), tenant=None, body=body)


def make_template(api, slug="studio", tier="FREE", presets=None):
    code, body = sa(api, "POST", T, {"slug": slug, "name": "Studio", "tier_required": tier,
                                     "base_renderer": "musician-band"})
    assert code == 201, body
    assert body["latest_version"] == 0 and body["published_version"] == 0
    code, v = sa(api, "POST", f"{T}/{slug}/versions",
                 {"tokens": {"primary": "#123456"}, "page_presets": presets or {"_home": DOC, "about": DOC}})
    assert code == 201 and v["version"] == 1, v
    code, head = sa(api, "POST", f"{T}/{slug}/publish", {"version": 1})
    assert code == 200 and head["published_version"] == 1
    return head


def test_admin_template_lifecycle(api):
    assert sa(api, "POST", T, {"slug": "Bad Slug"})[0] == 400
    assert sa(api, "POST", T, {"slug": "x", "base_renderer": "nope"})[0] == 400
    make_template(api)
    assert sa(api, "POST", T, {"slug": "studio"})[0] == 409

    # draft V2 inherits omitted fields from V1
    code, v2 = sa(api, "POST", f"{T}/studio/versions", {"tokens": {"primary": "#654321"}})
    assert code == 201 and v2["version"] == 2 and sorted(v2["page_presets"]) == ["_home", "about"]
    code, bad = sa(api, "POST", f"{T}/studio/versions", {"tokens": {"primary": "red"}})
    assert code == 400 and bad["path"] == "tokens.primary"
    code, bad = sa(api, "POST", f"{T}/studio/versions", {"components": {}})
    assert code == 400

    code, head = sa(api, "GET", f"{T}/studio")
    assert code == 200 and head["latest_version"] == 2 and head["published_version"] == 1
    assert head["versions"] == [{"version": 1, "created_at": head["versions"][0]["created_at"], "published": True},
                                {"version": 2, "created_at": head["versions"][1]["created_at"], "published": False}]
    assert sa(api, "GET", f"{T}/studio/versions/2")[1]["tokens"] == {"primary": "#654321"}
    assert sa(api, "GET", f"{T}/studio/versions/9")[0] == 404
    assert sa(api, "POST", f"{T}/studio/publish", {"version": 7})[0] == 400

    code, head = sa(api, "PUT", f"{T}/studio", {"name": "Studio 2", "tier_required": "PRO"})
    assert code == 200 and head["name"] == "Studio 2" and head["tier_required"] == "PRO"
    assert sa(api, "PUT", f"{T}/studio", {"base_renderer": "evil"})[0] == 400
    assert [t["slug"] for t in sa(api, "GET", T)[1]["templates"]] == ["studio"]  # no version rows


def test_preview_returns_sandbox_safe_html(api):
    make_template(api)
    code, body = sa(api, "POST", f"{T}/studio/preview", {})
    assert code == 200 and body["version"] == 1 and body["preset"] == "_home"
    html = body["html"]
    assert "<script" not in html and "<style>" in html and "--template-primary: #123456;" in html
    assert 'rel="stylesheet"' not in html  # CSS inlined, nothing to fetch
    about = sa(api, "POST", f"{T}/studio/preview", {"preset": "about"})[1]["html"]
    assert "About us" in about and "<script" not in about
    assert sa(api, "POST", f"{T}/studio/preview", {"preset": "nope"})[0] == 404
    assert sa(api, "POST", f"{T}/studio/preview", {"version": 5})[0] == 400
    assert api.storage.objects == {}  # no storage write


def test_deprecate_hides_from_tenant_list_but_site_keeps_working(api):
    make_template(api)
    sa(api, "POST", T, {"slug": "draft-only", "base_renderer": "personal-tech"})  # never published
    assert [t["slug"] for t in call("GET", "/api/templates", owner(api))[1]["templates"]] == ["studio"]

    code, body = call("POST", "/api/tenant/sites", owner(api), body={"name": "Band", "slug": "band",
                                                                     "template_id": "studio"})
    assert code == 201 and body["site"]["template_version"] == 1
    site_id = body["site"]["id"]
    assert sa(api, "PUT", f"{T}/studio", {"deprecated": True})[1]["deprecated"] is True
    assert call("GET", "/api/templates", owner(api))[1]["templates"] == []
    assert call("GET", f"/api/tenant/sites/{site_id}", owner(api))[1]["site"]["template_id"] == "studio"
    assert call("PUT", f"/api/tenant/sites/{site_id}", owner(api), body={"name": "Renamed", "template_id": "studio"})[0] == 200
    assert call("POST", "/api/tenant/sites", owner(api), body={"name": "New", "slug": "new", "template_id": "studio"})[0] == 400
    assert call("POST", "/api/tenant/sites", owner(api), body={"name": "N", "slug": "n2", "template_id": "draft-only"})[0] == 400
    assert sa(api, "PUT", f"{T}/studio", {"deprecated": False})[0] == 200
    assert [t["slug"] for t in call("GET", "/api/templates", owner(api))[1]["templates"]] == ["studio"]


def test_pin_update_available_and_update_to_published(api):
    make_template(api)
    site = call("POST", "/api/tenant/sites", owner(api), body={"name": "B", "slug": "b", "template_id": "studio"})[1]["site"]
    assert site["template_version"] == 1 and site["template_update_available"] is False
    sa(api, "POST", f"{T}/studio/versions", {"tokens": {"primary": "#000000"}})
    sa(api, "POST", f"{T}/studio/publish", {"version": 2})
    listed = call("GET", "/api/tenant/sites", owner(api))[1]["sites"][0]
    assert listed["template_version"] == 1 and listed["template_update_available"] is True

    path = f"/api/tenant/sites/{site['id']}/template-update"
    assert call("POST", path, tuser(role="member"))[0] == 403
    code, body = call("POST", path, owner(api))
    assert code == 200 and body["site"]["template_version"] == 2 and body["site"]["template_update_available"] is False


def test_bulk_upgrade_all_sites_on_template(api):
    make_template(api)
    api.table.put_item(Item={"pk": "TENANT#beta", "sk": "TENANT", "tier": "FREE", "name": "Beta"})
    a = call("POST", "/api/tenant/sites", owner(api), body={"name": "A", "slug": "sa", "template_id": "studio"})[1]["site"]
    store = DynamoDBTenantStore(api.table)
    b = store.put_site("beta", {"name": "B", "slug": "sb", "template_id": "studio", "template_version": 1})
    store.put_site("beta", {"name": "C", "slug": "sc", "template_id": "other"})
    sa(api, "POST", f"{T}/studio/versions", {})
    assert sa(api, "POST", f"{T}/studio/upgrade-sites", {"version": 9})[0] == 400

    code, body = sa(api, "POST", f"{T}/studio/upgrade-sites", {"version": 2})
    assert code == 200 and body["updated"] == 2
    assert {(s["tenant_slug"], s["site_id"]) for s in body["sites"]} == {("acme", a["id"]), ("beta", b["id"])}
    assert store.get_site("acme", a["id"])["template_version"] == 2
    assert store.get_site("beta", b["id"])["template_version"] == 2
    assert sa(api, "POST", f"{T}/studio/upgrade-sites", {"version": 2})[1]["updated"] == 0


def test_delete_refused_while_a_site_uses_template(api):
    make_template(api)
    site = call("POST", "/api/tenant/sites", owner(api), body={"name": "B", "slug": "b", "template_id": "studio"})[1]["site"]
    code, body = sa(api, "DELETE", f"{T}/studio")
    assert code == 409 and body["sites"] == 1
    call("DELETE", f"/api/tenant/sites/{site['id']}", owner(api))
    assert sa(api, "DELETE", f"{T}/studio")[0] == 204
    assert not [i for i in api.table.scan()["Items"] if i["sk"].startswith("TEMPLATE#studio")]


def test_apply_to_blocks_site_seeds_missing_preset_pages_only(api):
    make_template(api)
    site_id = call("POST", "/api/tenant/sites", owner(api), body={"name": "B", "slug": "b"})[1]["site"]["id"]
    call("PUT", f"/api/tenant/sites/{site_id}", owner(api), body={"editor": "blocks"})
    pages = f"/api/tenant/sites/{site_id}/pages"
    assert call("POST", pages, owner(api), body={"path": "about", "title": "Mine", "body": "<p>mine</p>"})[0] == 201

    code, body = call("PUT", f"/api/tenant/sites/{site_id}", owner(api), body={"template_id": "studio"})
    assert code == 200 and body["seeded_pages"] == ["_home"] and body["site"]["template_version"] == 1
    store = DynamoDBTenantStore(api.table)
    assert store.get_content("acme", site_id, "PAGE", "about")["body"] == "<p>mine</p>"  # untouched
    home = store.get_content("acme", site_id, "PAGE", "_home")
    assert home["status"] == "DRAFT" and json.loads(home["doc"])["root"]["props"]["title"] == "About us"


def test_apply_to_richtext_site_does_not_seed(api):
    make_template(api)
    site_id = call("POST", "/api/tenant/sites", owner(api), body={"name": "B", "slug": "b"})[1]["site"]["id"]
    call("PUT", f"/api/tenant/sites/{site_id}", owner(api), body={"editor": "richtext"})  # new sites default to blocks
    code, body = call("PUT", f"/api/tenant/sites/{site_id}", owner(api), body={"template_id": "studio"})
    assert code == 200 and "seeded_pages" not in body
    assert DynamoDBTenantStore(api.table).list_content("acme", site_id, "PAGE") == []


def test_template_css_resolves_data_only_template(api):
    make_template(api)
    from tests.test_template_css import _get
    from templates import get_renderer
    resp = _get("/api/templates/studio/css")
    assert resp["statusCode"] == 200 and resp["body"] == get_renderer("musician-band").render_site_css(blocks=True)
