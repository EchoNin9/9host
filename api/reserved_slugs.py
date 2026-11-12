"""
Platform hostnames that can never be tenant or site slugs (T-18).

Tenant and site slugs share one global namespace and both become ``{slug}.{domain}``
hostnames (site publish -> HostMappingKVS; ``middleware.extract_tenant_slug`` reads the
Host subdomain), so a slug equal to a platform label would shadow a platform host.
Mirrored in ``frontend/src/contexts/tenant-context.ts`` (``PLATFORM_SUBDOMAINS``).
"""

from __future__ import annotations

RESERVED_SLUGS: frozenset[str] = frozenset({
    "app",           # Admin SPA (production)
    "stage",         # Admin SPA (staging)
    "prod",          # retired Admin SPA host (draining)
    "www",
    "tools",
    "sites-origin",  # Cloudflare Worker -> sites CloudFront origin
    "proxy",         # Cloudflare for SaaS fallback origin
    "preview",       # standalone landing site staging
    "api",
    "admin",
})


def is_reserved_slug(slug: str | None) -> bool:
    return bool(slug) and str(slug).strip().lower() in RESERVED_SLUGS


def reserved_slug_error(slug: str) -> dict:
    """Response body for a rejected reserved slug."""
    return {"error": f"Slug '{slug}' is reserved for the platform.", "slug": slug, "code": "slug_reserved"}
