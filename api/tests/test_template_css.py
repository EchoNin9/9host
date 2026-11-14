"""GET /api/templates/{slug}/css — public template + block CSS for the block-editor canvas (T-31d)."""

import handler
from templates import TEMPLATE_RENDERERS, get_renderer


def _get(path, method="GET"):
    event = {"rawPath": path, "requestContext": {"http": {"method": method}, "requestId": "r"}, "headers": {}}
    return handler.lambda_handler(event, None)


def test_css_for_every_renderer_includes_block_styles():
    for slug in TEMPLATE_RENDERERS:
        resp = _get(f"/api/templates/{slug}/css")
        assert resp["statusCode"] == 200
        assert resp["headers"]["Content-Type"].startswith("text/css")
        assert "public" in resp["headers"]["Cache-Control"]
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
        assert resp["body"] == get_renderer(slug).render_site_css(blocks=True)
        assert ".b-hero" in resp["body"]


def test_css_needs_no_auth_or_tenant():
    resp = _get("/api/templates/BUSINESS-GENERIC/css/")  # case-insensitive slug, trailing slash
    assert resp["statusCode"] == 200


def test_unknown_slug_and_bad_paths_404():
    assert _get("/api/templates/nope/css")["statusCode"] == 404
    assert _get("/api/templates/business-generic")["statusCode"] == 404
    assert _get("/api/templates/business-generic/js")["statusCode"] == 404
    assert _get("/api/templates/business-generic/css", "POST")["statusCode"] == 405
