"""
Template layout system (Task 1.112, 1.113).

Maps template slugs to TemplateRenderer implementations.
Each template has its own HTML layout and CSS theme.
"""

import re

from .base_layout import TemplateRenderer, escape_html, media_url, rewrite_body_media_urls
from .musician_band import MusicianBandRenderer
from .personal_tech import PersonalTechRenderer
from .personal_resume import PersonalResumeRenderer
from .professional_services import ProfessionalServicesRenderer
from .business_generic import BusinessGenericRenderer

# Registry: template slug -> renderer class
TEMPLATE_RENDERERS: dict[str, type[TemplateRenderer]] = {
    "musician-band": MusicianBandRenderer,
    "personal-tech": PersonalTechRenderer,
    "personal-resume": PersonalResumeRenderer,
    "professional-services": ProfessionalServicesRenderer,
    "business-generic": BusinessGenericRenderer,
}


def get_renderer(template_slug: str) -> TemplateRenderer | None:
    """Get renderer for template slug. Returns None if not found."""
    slug = (template_slug or "").strip().lower()
    cls = TEMPLATE_RENDERERS.get(slug)
    if cls:
        return cls()
    return None


__all__ = [
    "TemplateRenderer",
    "TEMPLATE_RENDERERS",
    "get_renderer",
    "escape_html",
    "media_url",
    "rewrite_body_media_urls",
]
