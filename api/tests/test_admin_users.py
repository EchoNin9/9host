"""
T-20: GET /api/admin/users lists Cognito ``superadmin``-group members as ``platform_admins`` and
never as ``orphaned``. Orphaned stays for Cognito users with no tenant profile who are not
platform admins.
"""

import pytest

import admin_users_handler
from tests.test_handlers_integration import api, call, rsa_key, superadmin  # noqa: F401 (fixtures)


def _attrs(sub, email):
    return [{"Name": "sub", "Value": sub}, {"Name": "email", "Value": email}]


POOL_USERS = [
    {"Username": "adam", "Attributes": _attrs("sub-adam", "adam@echo9.net")},
    {"Username": "drift", "Attributes": _attrs("sub-drift", "drift@example.com")},
    {"Username": "owner-1", "Attributes": _attrs("owner-1", "o@acme.test")},
]


class FakeCognito:
    """Cognito pool: ``adam`` (no tenant) and ``owner-1`` (acme admin) are superadmins; ``drift`` is not."""

    def __init__(self, group_listing="ok"):
        self.group_listing = group_listing  # "ok" | "denied"
        self.calls = []

    def get_paginator(self, op):
        fake = self

        class P:
            def paginate(self, **kw):
                fake.calls.append((op, kw.get("GroupName")))
                if fake.group_listing == "broken":
                    raise RuntimeError("cognito unreachable")
                if op == "list_users_in_group":
                    if fake.group_listing == "denied":
                        raise RuntimeError("AccessDeniedException")
                    assert kw["GroupName"] == "superadmin"
                    return [{"Users": [POOL_USERS[0]]}, {"Users": [POOL_USERS[2]]}]
                return [{"Users": POOL_USERS[:2]}, {"Users": POOL_USERS[2:]}]

        return P()

    def admin_list_groups_for_user(self, UserPoolId, Username):
        self.calls.append(("admin_list_groups_for_user", Username))
        return {"Groups": [{"GroupName": "superadmin"}] if Username in ("adam", "owner-1") else []}


@pytest.fixture
def fake_cognito(monkeypatch):
    def install(mode="ok"):
        fake = FakeCognito(mode)
        real = admin_users_handler.boto3.client
        monkeypatch.setattr(admin_users_handler.boto3, "client",
                            lambda name, **kw: fake if name == "cognito-idp" else real(name, **kw))
        return fake

    return install


def test_superadmins_listed_as_platform_admins_not_orphaned(api, fake_cognito):
    fake = fake_cognito()
    code, body = call("GET", "/api/admin/users", superadmin(api), tenant=None)
    assert code == 200, body

    admins = {u["email"]: u for u in body["platform_admins"]}
    assert set(admins) == {"adam@echo9.net", "o@acme.test"}
    assert admins["adam@echo9.net"] == {
        "type": "cognito", "sub": "sub-adam", "email": "adam@echo9.net", "name": "",
        "role": "superadmin", "is_superadmin": True,
    }

    assert [u["email"] for u in body["orphaned"]] == ["drift@example.com"]
    assert body["orphaned"][0]["role"] is None and "username" not in body["orphaned"][0]

    # A superadmin who also has a tenant membership stays in the tenant grouping, flagged.
    acme = body["users_by_tenant"]["acme"]
    assert [(u["sub"], u.get("is_superadmin")) for u in acme] == [("owner-1", True)]

    # One group listing; no per-user group lookups.
    assert ("list_users_in_group", "superadmin") in fake.calls
    assert not [c for c in fake.calls if c[0] == "admin_list_groups_for_user"]


def test_fallback_when_list_users_in_group_denied(api, fake_cognito):
    fake = fake_cognito("denied")
    code, body = call("GET", "/api/admin/users", superadmin(api), tenant=None)
    assert code == 200, body
    assert [u["email"] for u in body["platform_admins"]] == ["adam@echo9.net"]
    assert body["platform_admins"][0]["role"] == "superadmin"
    assert [u["email"] for u in body["orphaned"]] == ["drift@example.com"]
    # Only users without a tenant profile are looked up (owner-1 is an acme member).
    assert [c[1] for c in fake.calls if c[0] == "admin_list_groups_for_user"] == ["adam", "drift"]


def test_cognito_unavailable_returns_empty_sections(api, fake_cognito):
    fake_cognito("broken")
    code, body = call("GET", "/api/admin/users", superadmin(api), tenant=None)
    assert code == 200
    assert body["platform_admins"] == [] and body["orphaned"] == []
    assert [u["sub"] for u in body["users_by_tenant"]["acme"]] == ["owner-1"]


def test_requires_superadmin(api):
    from tests.test_handlers_integration import owner

    assert call("GET", "/api/admin/users", owner(api), tenant=None)[0] == 403
