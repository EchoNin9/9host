"""
Personal Resume template (Task 1.113).

Single-page feel, timeline, skills bars. For resume/CV sites.
"""

from .base_layout import TemplateRenderer


class PersonalResumeRenderer(TemplateRenderer):
    """Professional resume style with timeline and section dividers."""

    def render_css(self) -> str:
        return """
/* Personal Resume template - professional CV style */
:root {
  --template-primary: #0369a1;
  --template-secondary: #0c4a6e;
  --template-bg: #ffffff;
  --template-surface: #f8fafc;
  --template-text: #0f172a;
  --template-muted: #475569;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--brand-font, 'Georgia', serif);
  background: var(--brand-bg, var(--template-bg));
  color: var(--brand-text, var(--template-text));
  line-height: 1.6;
  min-height: 100vh;
}

.site-header {
  background: var(--template-surface);
  padding: 1.25rem 2rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
  border-bottom: 1px solid #e2e8f0;
}
.site-logo { height: 44px; width: auto; }
.site-title {
  font-size: 1.35rem;
  font-weight: 600;
  color: var(--brand-primary, var(--template-primary));
}
.site-nav ul { display: flex; gap: 1.25rem; list-style: none; flex-wrap: wrap; }
.site-nav a {
  color: var(--template-muted);
  text-decoration: none;
  font-size: 0.9rem;
}
.site-nav a:hover { color: var(--brand-primary, var(--template-primary)); }

.main-content {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
}
.page-title {
  font-size: 1.5rem;
  margin-bottom: 1.25rem;
  color: var(--brand-primary, var(--template-primary));
  font-weight: 600;
  border-bottom: 2px solid var(--template-surface);
  padding-bottom: 0.5rem;
}
.page-nav ul { list-style: none; }
.page-nav a {
  display: block;
  padding: 0.4rem 0;
  color: var(--template-text);
  text-decoration: none;
}
.page-nav a:hover { color: var(--brand-primary, var(--template-primary)); }

.content { margin-top: 1rem; }
.content p { margin-bottom: 1rem; }
.content ul { margin-left: 1.5rem; margin-bottom: 1rem; }
.content img { max-width: 100%; height: auto; }

.posts-list, .events-list { list-style: none; }
.posts-list li, .events-list li {
  padding: 0.75rem 0;
  border-bottom: 1px solid #f1f5f9;
}
.posts-list a, .events-list a {
  color: var(--template-text);
  text-decoration: none;
}
.posts-list a:hover, .events-list a:hover {
  color: var(--brand-primary, var(--template-primary));
}

.media-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}
.media-gallery figure { margin: 0; }
.media-gallery img { width: 100%; height: auto; display: block; }
.media-gallery figcaption {
  font-size: 0.85rem;
  color: var(--template-muted);
  margin-top: 0.5rem;
}

@media (max-width: 640px) {
  .site-header { padding: 1rem; }
  .main-content { padding: 1rem; }
}
"""
