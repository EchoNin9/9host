"""
T-15: tenant-defined CustomRole (``ROLE#{name}``) permissions are enforced server-side.

A custom role whose ``permissions.sites`` is true grants content-editor access (content CRUD,
media upload URL, draft-publish); without it the caller is read-only (403 on writes). Built-in
roles keep their behaviour. Roles are created through the real ``/api/tenant/roles`` API.
"""

import pytest

from tenant_store import DynamoDBTenantStore
from tests.test_handlers_integration import (  # noqa: F401 - pytest fixtures
    api,
    call,
    cognito,
    create_site,
    owner,
    rsa_key,
    tuser,
)


def make_role(api, name, **perms):
    code, body = call("POST", "/api/tenant/roles", owner(api), body={"name": name, "permissions": perms})
    assert code == 201, body


def cognito_member(api, sub, role):
    DynamoDBTenantStore(api.table).put_member("acme", {"sub": sub, "role": role, "name": sub})
    return cognito(api.key, sub)


@pytest.fixture
def roles(api):
    make_role(api, "writer", sites=True)
    make_role(api, "viewer", analytics=True)
    return api


def _content_writes(site_id, token):
    base = f"/api/tenant/sites/{site_id}"
    return [
        call("POST", f"{base}/pages", token, body={"path": "news", "title": "News"})[0],
        call("PUT", f"{base}/pages/news", token, body={"title": "Latest"})[0],
        call("POST", f"{base}/posts", token, body={"slug": "hello", "title": "Hello"})[0],
        call("POST", f"{base}/upload-url", token, body={"content_length": 10, "filename": "a.png"})[0],
    ]


@pytest.mark.parametrize("kind", ["tuser", "cognito"])
def test_custom_role_with_sites_permission_can_edit_content(roles, kind):
    site_id = create_site(roles)
    token = tuser("wally", role="writer") if kind == "tuser" else cognito_member(roles, "w-1", "writer")
    assert _content_writes(site_id, token) == [201, 200, 201, 200]
    assert call("DELETE", f"/api/tenant/sites/{site_id}/pages/news", token)[0] == 204
    assert call("GET", f"/api/tenant/sites/{site_id}/draft-token", token)[0] == 200
    # Passes the role gate; fails later only because the test site has no template.
    assert call("POST", f"/api/tenant/sites/{site_id}/draft-publish", token)[0] == 400


@pytest.mark.parametrize("kind", ["tuser", "cognito"])
def test_custom_role_without_sites_permission_gets_403(roles, kind):
    site_id = create_site(roles)
    token = tuser("vic", role="viewer") if kind == "tuser" else cognito_member(roles, "v-1", "viewer")
    assert call("GET", f"/api/tenant/sites/{site_id}/pages", token)[0] == 200  # reads stay open
    assert _content_writes(site_id, token) == [403, 403, 403, 403]
    assert call("GET", f"/api/tenant/sites/{site_id}/draft-token", token)[0] == 403
    assert call("POST", f"/api/tenant/sites/{site_id}/draft-publish", token)[0] == 403


def test_custom_role_permission_changes_take_effect_and_unknown_role_denied(roles):
    site_id = create_site(roles)
    base = f"/api/tenant/sites/{site_id}/pages"
    writer = tuser("wally", role="writer")
    assert call("POST", base, writer, body={"path": "a"})[0] == 201
    assert call("PUT", "/api/tenant/roles/writer", owner(roles), body={"permissions": {"sites": False}})[0] == 200
    assert call("POST", base, writer, body={"path": "b"})[0] == 403
    # A role name with no ROLE# row (e.g. deleted) grants nothing.
    assert call("POST", base, tuser("ghost", role="ghost"), body={"path": "c"})[0] == 403


def test_custom_role_does_not_gain_manager_routes(roles):
    site_id = create_site(roles)
    writer = tuser("wally", role="writer")
    assert call("POST", f"/api/tenant/sites/{site_id}/publish", writer)[0] == 403
    assert call("POST", "/api/tenant/sites", writer, body={"name": "Nope"})[0] == 403
    assert call("GET", "/api/tenant/roles", writer)[0] == 403


@pytest.mark.parametrize("role,expected", [("admin", 201), ("manager", 201), ("editor", 201), ("member", 403)])
def test_builtin_roles_unchanged(roles, role, expected):
    site_id = create_site(roles)
    assert call("POST", f"/api/tenant/sites/{site_id}/pages", tuser(role=role), body={"path": "x"})[0] == expected
    # A tenant cannot shadow a built-in role with a ROLE# row (names are reserved).
    assert call("POST", "/api/tenant/roles", owner(roles), body={"name": role, "permissions": {}})[0] == 400


class _CountingTable:
    def __init__(self, items):
        self.items, self.reads = items, []

    def get_item(self, Key):
        self.reads.append(Key["sk"])
        item = self.items.get(Key["sk"])
        return {"Item": item} if item else {}


def _ctx(role, table):
    import request_context as rc

    principal = rc.Principal(kind="tuser", identifier="u", email=None, is_superadmin=False)
    return rc.RequestContext(event={}, principal=principal, tenant_slug="acme", effective_role=role,
                             is_impersonating=False, _table=table)


def test_require_permission_reads_role_row_once_and_never_for_builtins():
    import request_context as rc

    table = _CountingTable({"ROLE#writer": {"permissions": {"sites": True}}})
    ctx = _ctx("writer", table)
    assert ctx.require_permission("sites", ("admin",)) == ("acme", "writer")
    assert ctx.require_permission("sites", ("admin",)) == ("acme", "writer")
    with pytest.raises(rc.HttpError) as e:
        ctx.require_permission("users", ("admin",))
    assert e.value.status == 403
    assert table.reads == ["ROLE#writer"]

    for role in ("admin", "manager", "editor", "member"):
        builtin = _ctx(role, table)
        if role == "member":
            with pytest.raises(rc.HttpError):
                builtin.require_permission("sites", ("admin", "manager", "editor"))
        else:
            assert builtin.require_permission("sites", ("admin", "manager", "editor"))[1] == role
    assert table.reads == ["ROLE#writer"]
