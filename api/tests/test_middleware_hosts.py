"""T-18: platform hosts (app./stage./prod./www./... and the apex) never resolve a tenant."""
import pytest

from middleware import extract_tenant_slug
from reserved_slugs import RESERVED_SLUGS


def _ev(host, path="/api/tenant"):
    return {"headers": {"host": host}, "rawPath": path}


@pytest.mark.parametrize("host", ["app.echo9.net", "APP.echo9.net", "stage.echo9.net", "prod.echo9.net",
                                  "www.echo9.net", "echo9.net", "app.echo9.ca", "preview.echo9.net"])
def test_platform_hosts_have_no_tenant(host):
    assert extract_tenant_slug(_ev(host), domains="echo9.net,echo9.ca") is None


@pytest.mark.parametrize("label", sorted(RESERVED_SLUGS))
def test_every_reserved_label_is_a_platform_host(label):
    assert extract_tenant_slug(_ev(f"{label}.echo9.net"), domains="echo9.net") is None


def test_tenant_subdomain_still_resolves():
    assert extract_tenant_slug(_ev("acme.echo9.net"), domains="echo9.net") == "acme"
    assert extract_tenant_slug(_ev("acme.echo9.net")) == "acme"  # default domain


def test_header_still_wins_on_platform_host():
    ev = _ev("app.echo9.net")
    ev["headers"]["x-tenant-slug"] = "acme"
    assert extract_tenant_slug(ev, domains="echo9.net") == "acme"
