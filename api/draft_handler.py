"""
Draft preview token API (Task 1.117).

GET /api/tenant/sites/{id}/draft-token — HS256 JWT for the draft preview URL (1 hour),
admin/manager/editor only. The signing key comes from secrets_cache (Bug #7).
"""

import os
from datetime import datetime, timedelta, timezone

import jwt

import secrets_cache
from publish_handler import CONTENT_ROLES, _base_domain, load_site
from request_context import RequestContext, respond


def draft_token_handler(ctx: RequestContext) -> dict:
    _, tenant_slug, site_id, site = load_site(ctx, "draft-token", CONTENT_ROLES)
    site_slug = (site.get("slug") or "").strip()
    if not site_slug:
        return respond(400, {"error": "Site has no slug."})
    secret = secrets_cache.get_secret_string(os.environ.get("JWT_SECRET_ARN"))
    if not secret or secret == "REPLACE_ME":
        return respond(503, {"error": "Draft preview is not configured."})

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "tenant_slug": tenant_slug,
            "site_id": site_id,
            "type": "draft",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )
    preview_url = f"https://{site_slug}.{_base_domain()}/preview?token={token}"
    return respond(200, {"token": token, "preview_url": preview_url, "expires_in": 3600})
