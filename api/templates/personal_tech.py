"""
Personal Tech template (Task 1.113).

Clean, code-friendly, project cards. For developer/tech portfolios.
"""

from .base_layout import TemplateRenderer


class PersonalTechRenderer(TemplateRenderer):
    """Light theme, monospace accents, clean typography."""

    def render_css(self) -> str:
        return """
/* Personal Tech template - clean developer style */
:root {
  --template-primary: #0d9488;
  --template-secondary: #64748b;
  --template-bg: #fafafa;
  --template-surface: #ffffff;
  --template-text: #1e293b;
  --template-muted: #64748b;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--brand-font, 'JetBrains Mono', 'Fira Code', monospace);
  background: var(--brand-bg, var(--template-bg));
  color: var(--brand-text, var(--template-text));
  line-height: 1.7;
  min-height: 100vh;
}

.site-header {
  background: var(--template-surface);
  padding: 1rem 2rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.site-logo { height: 40px; width: auto; }
.site-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--brand-primary, var(--template-primary));
  font-family: var(--brand-font, 'JetBrains Mono', monospace);
}
.site-nav ul { display: flex; gap: 1.5rem; list-style: none; flex-wrap: wrap; }
.site-nav a {
  color: var(--template-muted);
  text-decoration: none;
  font-size: 0.9rem;
}
.site-nav a:hover { color: var(--brand-primary, var(--template-primary)); }

.main-content {
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem;
}
.page-title {
  font-size: 1.75rem;
  margin-bottom: 1.5rem;
  color: var(--brand-primary, var(--template-primary));
  font-weight: 600;
}
.page-nav ul { list-style: none; }
.page-nav a {
  display: block;
  padding: 0.5rem 0;
  color: var(--template-text);
  text-decoration: none;
  font-size: 0.95rem;
}
.page-nav a:hover { color: var(--brand-primary, var(--template-primary)); }

.content { margin-top: 1rem; }
.content p { margin-bottom: 1rem; }
.content pre {
  background: var(--template-surface);
  padding: 1rem;
  overflow-x: auto;
  border-radius: 4px;
  font-size: 0.875rem;
}
.content code { font-family: inherit; }
.content img { max-width: 100%; height: auto; }

.posts-list, .events-list { list-style: none; }
.posts-list li, .events-list li {
  padding: 0.75rem 0;
  border-bottom: 1px solid #e2e8f0;
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
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
}
.media-gallery figure { margin: 0; }
.media-gallery img { width: 100%; height: auto; display: block; border-radius: 4px; }
.media-gallery figcaption {
  font-size: 0.8rem;
  color: var(--template-muted);
  margin-top: 0.25rem;
}

@media (max-width: 640px) {
  .site-header { padding: 1rem; }
  .main-content { padding: 1rem; }
}
"""
