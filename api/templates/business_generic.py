"""
Business Generic template (Task 1.113).

Features grid, team section, CTA. For generic business sites.
"""

from .base_layout import TemplateRenderer


class BusinessGenericRenderer(TemplateRenderer):
    """Business style with features grid and team section."""

    def render_css(self) -> str:
        return """
/* Business Generic template - features grid, team, CTA */
:root {
  --template-primary: #059669;
  --template-secondary: #10b981;
  --template-bg: #ffffff;
  --template-surface: #f9fafb;
  --template-text: #111827;
  --template-muted: #6b7280;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--brand-font, 'Segoe UI', Tahoma, sans-serif);
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
  border-bottom: 2px solid var(--brand-primary, var(--template-primary));
}
.site-logo { height: 48px; width: auto; }
.site-title {
  font-size: 1.5rem;
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
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem;
}
.page-title {
  font-size: 1.75rem;
  margin-bottom: 1.5rem;
  color: var(--brand-primary, var(--template-primary));
  font-weight: 700;
}
.page-nav ul { list-style: none; display: flex; flex-wrap: wrap; gap: 1rem; }
.page-nav a {
  display: inline-block;
  padding: 0.5rem 1rem;
  color: var(--template-text);
  text-decoration: none;
  background: var(--template-surface);
  border-radius: 6px;
}
.page-nav a:hover {
  background: var(--brand-primary, var(--template-primary));
  color: white;
}

.content { margin-top: 1rem; }
.content p { margin-bottom: 1rem; }
.content img { max-width: 100%; height: auto; }

.posts-list, .events-list { list-style: none; }
.posts-list li, .events-list li {
  padding: 1rem 0;
  border-bottom: 1px solid #e5e7eb;
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
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1.5rem;
}
.media-gallery figure { margin: 0; }
.media-gallery img { width: 100%; height: auto; display: block; border-radius: 8px; }
.media-gallery figcaption {
  font-size: 0.875rem;
  color: var(--template-muted);
  margin-top: 0.5rem;
}

@media (max-width: 640px) {
  .site-header { padding: 1rem; }
  .main-content { padding: 1rem; }
  .page-nav ul { flex-direction: column; }
}
"""
