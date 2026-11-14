"""T-31b: legacy sites compile byte-identically after the block-core change.

fixtures/legacy_bundle_hashes.json was captured from the pre-T-31b compiler (HEAD 282a934) over every
existing compiler fixture (all templates x live/draft) plus edge variants. Regenerate ONLY when an
intentional legacy output change is made:  UPDATE_LEGACY_HASHES=1 ../.venv/bin/pytest tests/test_blocks_legacy.py
"""

import hashlib
import json
import os
from pathlib import Path

import pytest

from site_compiler import compile_site
from templates import TEMPLATE_RENDERERS
from tests.test_site_compiler import make_snapshot

HASHES = Path(__file__).parent / "fixtures" / "legacy_bundle_hashes.json"
TEMPLATES = sorted(TEMPLATE_RENDERERS)

LINKY_BODY = (
    '<p>See <a href="/about/">about</a>, <a href="//cdn.example/x">proto-rel</a>, '
    '<a href="https://example.com/" target="_blank">ext</a> &amp; <a href="#top">anchor</a></p>'
    '<img src="https://bucket.s3.amazonaws.com/acme/s1/pic.png?X-Amz=1" alt="p">'
)
# A page row that already carries a block doc: legacy sites (editor unset / "richtext") ignore it.
DOC = json.dumps({"schema": 1, "root": {"props": {}}, "content": [
    {"type": "Hero", "props": {"id": "h", "heading": "DOC SHOULD NOT RENDER"}}]})


def _variants():
    v = {}
    for slug in TEMPLATES:
        v[f"{slug}/xss"] = make_snapshot(slug)
        v[f"{slug}/links"] = make_snapshot(slug, body=LINKY_BODY)
    v["empty"] = make_snapshot(pages=[], posts=[], events=[], media=[])
    v["escaped-path"] = make_snapshot(pages=[{"path": 'x"><script>alert(1)</script>', "title": "<b>t</b>", "body": ""}])
    v["forked"] = make_snapshot(template={"slug": "my-fork", "forked_from": "personal-tech"})
    v["branding-bad"] = make_snapshot(site={"name": "A", "slug": "a", "branding": {
        "primary_color": "red;}body{display:none", "text_color": "#ABC", "font_family": "Arial;}</style>"}})
    v["doc-ignored"] = make_snapshot(pages=[{"path": "about", "title": "About", "body": LINKY_BODY, "doc": DOC}])
    v["doc-ignored-richtext"] = make_snapshot(
        site={"name": "Acme", "slug": "acme-band", "editor": "richtext", "branding": {}},
        pages=[{"path": "about", "title": "About", "body": LINKY_BODY, "doc": DOC},
               {"path": "_home", "title": "Home", "body": "<p>h</p>", "doc": DOC}])
    return v


def _bundle_hashes(snapshot, mode):
    bundle = compile_site(snapshot, mode=mode)
    return {p: hashlib.sha256(b).hexdigest() for p, b in sorted(bundle.files.items())}


def _current():
    return {f"{name}/{mode}": _bundle_hashes(snap, mode)
            for name, snap in _variants().items() for mode in ("live", "draft")}


def test_legacy_bundles_byte_identical():
    current = _current()
    if os.environ.get("UPDATE_LEGACY_HASHES"):
        HASHES.parent.mkdir(parents=True, exist_ok=True)
        HASHES.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n")
        pytest.skip("legacy hashes regenerated")
    expected = json.loads(HASHES.read_text())
    assert set(current) == set(expected)
    for key in expected:
        assert current[key] == expected[key], key
