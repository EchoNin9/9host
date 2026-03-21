"""
Shared path construction utilities (Task 1.144).

Centralizes URL path patterns used by publish and draft-publish flows.
"""


def site_base_path(tenant_slug: str, site_id: str) -> str:
    """Return the site_base prefix for published site internal links.

    Published sites are served under /site/{tenant}/{site_id}/ on CloudFront.
    All internal links (nav, blog, events, gallery) must use this prefix so
    they resolve correctly rather than hitting the SPA.

    Draft preview uses an empty site_base because the CF preview function
    rewrites paths — call this only for published renders.
    """
    return f"/site/{tenant_slug}/{site_id}"


def media_base_url(tenant_slug: str, site_id: str, cloudfront_media_url: str = "/media/") -> str:
    """Return the media URL base for a given tenant/site.

    Media files are served at /media/{tenant}/{site}/{filename} via CloudFront.
    """
    base = cloudfront_media_url.rstrip("/")
    return f"{base}/{tenant_slug}/{site_id}"
