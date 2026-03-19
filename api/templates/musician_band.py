"""
Musician/Band template (Task 1.113).

Dark theme, hero image, tour dates grid. For band/artist sites.
"""

from .base_layout import TemplateRenderer


class MusicianBandRenderer(TemplateRenderer):
    """Dark theme with accent colors, sidebar-style nav, tour dates grid."""

    def render_css(self) -> str:
        return """
/* Musician/Band template - dark theme */
:root {
  --template-primary: #e11d48;
  --template-secondary: #7c3aed;
  --template-bg: #0f0f0f;
  --template-surface: #1a1a1a;
  --template-text: #f5f5f5;
  --template-muted: #a3a3a3;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--brand-font, 'Inter', sans-serif);
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
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem;
}
.page-title {
  font-size: 2rem;
  margin-bottom: 1.5rem;
  color: var(--brand-primary, var(--template-primary));
}
.page-nav ul { list-style: none; }
.page-nav a {
  display: block;
  padding: 0.5rem 0;
  color: var(--template-text);
  text-decoration: none;
  border-bottom: 1px solid var(--template-surface);
}
.page-nav a:hover { color: var(--brand-primary, var(--template-primary)); }

.content { margin-top: 1rem; }
.content p { margin-bottom: 1rem; }
.content img { max-width: 100%; height: auto; }

.posts-list, .events-list { list-style: none; }
.posts-list li, .events-list li {
  padding: 1rem 0;
  border-bottom: 1px solid var(--template-surface);
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
