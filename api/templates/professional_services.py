"""
Professional Services template (Task 1.113).

Corporate, case study cards. For consultant/agency sites.
"""

from .base_layout import TemplateRenderer


class ProfessionalServicesRenderer(TemplateRenderer):
    """Corporate style with case study cards and professional typography."""

    def render_css(self) -> str:
        return """
/* Professional Services template - corporate consultant style */
:root {
  --template-primary: #1e40af;
  --template-secondary: #3b82f6;
  --template-bg: #f1f5f9;
  --template-surface: #ffffff;
  --template-text: #1e293b;
  --template-muted: #64748b;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--brand-font, 'Helvetica Neue', Arial, sans-serif);
  background: var(--brand-bg, var(--template-bg));
  color: var(--brand-text, var(--template-text));
  line-height: 1.6;
  min-height: 100vh;
}

.site-header {
  background: var(--template-surface);
  padding: 1rem 2rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
  box-shadow: 0 2px 4px rgba(0,0,0,0.06);
}
.site-logo { height: 48px; width: auto; }
.site-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--brand-primary, var(--template-primary));
}
.site-nav ul { display: flex; gap: 1.5rem; list-style: none; flex-wrap: wrap; }
.site-nav a {
  color: var(--template-muted);
  text-decoration: none;
  font-weight: 500;
}
.site-nav a:hover { color: var(--brand-primary, var(--template-primary)); }

.main-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 2rem;
}
.page-title {
  font-size: 2rem;
  margin-bottom: 1.5rem;
  color: var(--brand-primary, var(--template-primary));
  font-weight: 700;
}
.page-nav ul { list-style: none; }
.page-nav a {
  display: block;
  padding: 0.5rem 0;
  color: var(--template-text);
  text-decoration: none;
}
.page-nav a:hover { color: var(--brand-primary, var(--template-primary)); }

.content { margin-top: 1rem; }
.content p { margin-bottom: 1rem; }
.content img { max-width: 100%; height: auto; }

.posts-list, .events-list { list-style: none; }
.posts-list li, .events-list li {
  padding: 1rem;
  margin-bottom: 0.5rem;
  background: var(--template-surface);
  border-radius: 6px;
  border-left: 4px solid var(--brand-primary, var(--template-primary));
}
.posts-list a, .events-list a {
  color: var(--template-text);
  text-decoration: none;
  font-weight: 500;
}
.posts-list a:hover, .events-list a:hover {
  color: var(--brand-primary, var(--template-primary));
}

.media-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1.5rem;
}
.media-gallery figure {
  margin: 0;
  background: var(--template-surface);
  padding: 0.5rem;
  border-radius: 6px;
}
.media-gallery img { width: 100%; height: auto; display: block; }
.media-gallery figcaption {
  font-size: 0.875rem;
  color: var(--template-muted);
  margin-top: 0.5rem;
}

@media (max-width: 640px) {
  .site-header { padding: 1rem; }
  .main-content { padding: 1rem; }
}
"""
