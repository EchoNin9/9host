"""
TenantStore behavioural tests (T-03), run against both InMemoryTenantStore and a
moto-backed DynamoDBTenantStore.
"""
import pytest

from tenant_store import DynamoDBTenantStore, InMemoryTenantStore


@pytest.fixture(params=["memory", "dynamodb"])
def store_and_raw(request):
    """Yields (store, put_raw) where put_raw writes a raw pk/sk item (for legacy seeding)."""
    if request.param == "memory":
        store = InMemoryTenantStore()
        yield store, store._put
    else:
        table = request.getfixturevalue("dynamodb_table")
        yield DynamoDBTenantStore(table), lambda item: table.put_item(Item=item)


@pytest.fixture
def store(store_and_raw):
    return store_and_raw[0]


def _seed_tenant(put_raw, slug, **attrs):
    put_raw({"pk": f"TENANT#{slug}", "sk": "TENANT", "name": slug, "tier": "FREE", **attrs})


# --- Bug #3: SITE_META# ----------------------------------------------------------

def test_list_sites_ignores_content_rows(store):
    a = store.put_site("acme", {"name": "A", "slug": "acme-a"})
    b = store.put_site("acme", {"name": "B", "slug": "acme-b"})
    for site in (a, b):
        store.put_content("acme", site["id"], "PAGE", {"path": "home", "title": "Home"})
        store.put_content("acme", site["id"], "POST", {"title": "Hello"})
        store.put_content("acme", site["id"], "EVENT", {"title": "Gig"})
        store.put_content("acme", site["id"], "MEDIA", {"filename": "x.png"})

    sites = store.list_sites("acme")
    assert sorted(s["id"] for s in sites) == sorted([a["id"], b["id"]])
    assert {s["name"] for s in sites} == {"A", "B"}
    assert all("pk" not in s and "sk" not in s for s in sites)


def test_put_site_mirrors_to_legacy_sk(store_and_raw):
    store, _ = store_and_raw
    site = store.put_site("acme", {"name": "A", "slug": "acme-a"})
    # Raw read through the backend primitive: both rows exist.
    assert store._get("TENANT#acme", f"SITE_META#{site['id']}") is not None
    legacy = store._get("TENANT#acme", f"SITE#{site['id']}")
    assert legacy is not None and legacy["gsi4pk"] == "SLUG#acme-a"


def test_legacy_only_sites_still_list_and_backfill(store_and_raw):
    store, put_raw = store_and_raw
    put_raw({"pk": "TENANT#acme", "sk": "SITE#old1", "name": "Old", "slug": "old-one",
             "gsi4pk": "SLUG#old-one", "gsi4sk": "SITE#old1"})
    put_raw({"pk": "TENANT#acme", "sk": "SITE#old1#PAGE#home", "path": "home", "title": "Home"})
    put_raw({"pk": "TENANT#acme", "sk": "SITE#old1#POST#p1", "id": "p1"})
    new = store.put_site("acme", {"name": "New", "slug": "new-one"})

    sites = store.list_sites("acme")
    assert sorted(s["id"] for s in sites) == sorted(["old1", new["id"]])
    # Backfilled: meta row now exists and a second listing returns the same.
    assert store._get("TENANT#acme", "SITE_META#old1")["name"] == "Old"
    assert sorted(s["id"] for s in store.list_sites("acme")) == sorted(["old1", new["id"]])
    # bySiteSlug still resolves the legacy site exactly once.
    assert store.resolve_site_slug("old-one") == {"tenant_slug": "acme", "site_id": "old1"}


def test_get_site_falls_back_to_legacy_row(store_and_raw):
    store, put_raw = store_and_raw
    put_raw({"pk": "TENANT#acme", "sk": "SITE#old1", "name": "Old", "slug": "old-one"})
    site = store.get_site("acme", "old1")
    assert site["id"] == "old1" and site["name"] == "Old"
    assert store._get("TENANT#acme", "SITE_META#old1") is not None


# --- Bug #4: storage counter --------------------------------------------------------

def test_adjust_storage_bytes_never_underflows(store_and_raw):
    store, put_raw = store_and_raw
    _seed_tenant(put_raw, "acme", storage_used_bytes=100)
    assert store.adjust_storage_bytes("acme", 50) == 150
    assert store.adjust_storage_bytes("acme", -30) == 120
    assert store.adjust_storage_bytes("acme", -120) == 0
    assert store.adjust_storage_bytes("acme", -500) == 0
    assert store.get_tenant("acme")["storage_used_bytes"] == 0


def test_adjust_storage_bytes_missing_attribute(store_and_raw):
    store, put_raw = store_and_raw
    _seed_tenant(put_raw, "acme")
    assert store.adjust_storage_bytes("acme", -10) == 0
    assert store.adjust_storage_bytes("acme", 10) == 10


# --- Tenant metadata ---------------------------------------------------------------

def test_get_and_update_tenant(store_and_raw):
    store, put_raw = store_and_raw
    assert store.get_tenant("acme") is None
    _seed_tenant(put_raw, "acme")
    updated = store.update_tenant("acme", {"tier": "PRO", "name": "Acme Inc"})
    assert updated["tier"] == "PRO" and updated["name"] == "Acme Inc" and updated["slug"] == "acme"
    assert store.get_tenant("acme")["tier"] == "PRO"
    with pytest.raises(KeyError):
        store.update_tenant("ghost", {"tier": "PRO"})


# --- Tenant isolation --------------------------------------------------------------

def test_tenant_partition_isolation(store):
    a_site = store.put_site("tenant-a", {"name": "A", "slug": "a-site"})
    store.put_content("tenant-a", a_site["id"], "POST", {"id": "p1", "title": "secret"})
    store.put_site("tenant-b", {"name": "B", "slug": "b-site"})

    assert [s["name"] for s in store.list_sites("tenant-b")] == ["B"]
    assert store.get_site("tenant-b", a_site["id"]) is None
    assert store.get_content("tenant-b", a_site["id"], "POST", "p1") is None
    assert store.list_content("tenant-b", a_site["id"], "POST") == []
    assert store.delete_content("tenant-b", a_site["id"], "POST", "p1") is None
    store.delete_site_cascade("tenant-b", a_site["id"])
    assert store.get_site("tenant-a", a_site["id"]) is not None
    assert store.get_content("tenant-a", a_site["id"], "POST", "p1")["title"] == "secret"


# --- Site / content CRUD -----------------------------------------------------------

def test_site_crud(store):
    site = store.put_site("acme", {"name": "A", "slug": "a-site", "status": "draft"})
    assert store.get_site("acme", site["id"])["status"] == "draft"
    store.put_site("acme", {**site, "status": "published"})
    assert store.get_site("acme", site["id"])["status"] == "published"
    assert len(store.list_sites("acme")) == 1


def test_content_crud_and_status_filter(store):
    site = store.put_site("acme", {"name": "A", "slug": "a-site"})
    sid = site["id"]
    page = store.put_content("acme", sid, "page", {"path": "about", "title": "About", "status": "DRAFT"})
    assert page["path"] == "about"
    post = store.put_content("acme", sid, "POST", {"title": "One", "status": "PUBLISHED"})
    store.put_content("acme", sid, "POST", {"title": "Two", "status": "DRAFT"})

    assert store.get_content("acme", sid, "PAGE", "about")["title"] == "About"
    assert len(store.list_content("acme", sid, "POST")) == 2
    assert [p["title"] for p in store.list_content("acme", sid, "POST", status="published")] == ["One"]
    assert store.list_content("acme", sid, "EVENT") == []

    deleted = store.delete_content("acme", sid, "POST", post["id"])
    assert deleted["title"] == "One"
    assert store.get_content("acme", sid, "POST", post["id"]) is None
    assert store.delete_content("acme", sid, "POST", post["id"]) is None

    with pytest.raises(ValueError):
        store.list_content("acme", sid, "WIDGET")


def test_delete_site_cascade(store):
    keep = store.put_site("acme", {"name": "Keep", "slug": "keep"})
    gone = store.put_site("acme", {"name": "Gone", "slug": "gone"})
    for site in (keep, gone):
        store.put_content("acme", site["id"], "PAGE", {"path": "home"})
        store.put_content("acme", site["id"], "MEDIA", {"id": "m1"})

    store.delete_site_cascade("acme", gone["id"])

    assert [s["id"] for s in store.list_sites("acme")] == [keep["id"]]
    assert store.get_site("acme", gone["id"]) is None
    assert store.list_content("acme", gone["id"], "PAGE") == []
    assert store.list_content("acme", gone["id"], "MEDIA") == []
    assert store.resolve_site_slug("gone") is None
    assert store.get_content("acme", keep["id"], "MEDIA", "m1") is not None


def test_resolve_site_slug(store):
    site = store.put_site("acme", {"name": "A", "slug": "My-Band"})
    assert store.resolve_site_slug("my-band") == {"tenant_slug": "acme", "site_id": site["id"]}
    assert store.resolve_site_slug("  MY-BAND ") == {"tenant_slug": "acme", "site_id": site["id"]}
    assert store.resolve_site_slug("nope") is None
    assert store.resolve_site_slug("") is None


# --- Hybrid auth entities ----------------------------------------------------------

def test_members_tusers_roles(store_and_raw):
    store, put_raw = store_and_raw
    put_raw({"pk": "TENANT#acme", "sk": "USER#sub1#PROFILE", "sub": "sub1", "role": "Admin"})
    put_raw({"pk": "TENANT#acme", "sk": "USER#sub1#PERMISSIONS", "permissions": {"sites": True}})
    put_raw({"pk": "TENANT#acme", "sk": "USER#sub2#PROFILE", "sub": "sub2"})
    put_raw({"pk": "TENANT#acme", "sk": "TUSER#jane", "username": "jane", "password_hash": "x", "role": "member"})
    put_raw({"pk": "TENANT#acme", "sk": "ROLE#editor", "name": "editor", "permissions": {"sites": True}})
    put_raw({"pk": "TENANT#other", "sk": "USER#sub3#PROFILE", "sub": "sub3", "role": "admin"})
    put_raw({"pk": "TENANT#other", "sk": "TUSER#bob", "username": "bob"})
    put_raw({"pk": "TENANT#other", "sk": "ROLE#viewer", "name": "viewer"})

    assert store.get_member_role("acme", "sub1") == "admin"
    assert store.get_member_role("acme", "sub2") == "member"
    assert store.get_member_role("acme", "sub3") is None

    assert sorted(m["sub"] for m in store.list_cognito_members("acme")) == ["sub1", "sub2"]
    tusers = store.list_tusers("acme")
    assert [t["username"] for t in tusers] == ["jane"]
    assert "password_hash" not in tusers[0]
    assert [r["name"] for r in store.list_roles("acme")] == ["editor"]
