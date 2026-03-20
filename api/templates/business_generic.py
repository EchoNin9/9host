"""
Business Generic template (Task 1.113).

Features grid, team section, CTA. For generic business sites.
"""

from .base_layout import TemplateRenderer


class BusinessGenericRenderer(TemplateRenderer):
    """Business style with features grid and team section."""

    def render_css(self) -> str:
        return """
/* Business Generic template — professional light theme, CTA hero, service cards */
:root {
  --template-primary: #2563eb;
  --template-secondary: #3b82f6;
  --template-bg: #fafbfc;
  --template-surface: #ffffff;
  --template-text: #1f2937;
  --template-muted: #6b7280;
  --template-border: #e5e7eb;
  --template-heading: #1e3a5f;
}

/* ── Reset & Body ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 16px; scroll-behavior: smooth; }
body {
  font-family: var(--brand-font, 'Inter', system-ui, -apple-system, sans-serif);
  background: var(--brand-bg, var(--template-bg));
  color: var(--brand-text, var(--template-text));
  line-height: 1.6;
  min-height: 100vh;
}
img { max-width: 100%; height: auto; display: block; }
a { color: var(--brand-primary, var(--template-primary)); text-decoration: none; }
a:hover { color: #1d4ed8; text-decoration: underline; }
ul, ol { list-style: none; }

/* ── Site Wrapper (sticky footer) ── */
.site-wrapper { min-height: 100vh; display: flex; flex-direction: column; }

/* ── Header — clean professional ── */
.site-header {
  background: var(--template-surface);
  padding: 1rem 2rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
  border-bottom: 2px solid var(--template-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.site-logo { height: 44px; width: auto; border-radius: 6px; }
.site-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--template-heading);
  font-family: 'Georgia', 'Times New Roman', serif;
}
.site-nav ul { display: flex; gap: 1.5rem; list-style: none; flex-wrap: wrap; }
.site-nav a {
  color: var(--template-muted);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s;
}
.site-nav a:hover { color: var(--brand-primary, var(--template-primary)); text-decoration: none; }

/* ── Hero — CTA-focused blue gradient ── */
.hero {
  padding: 5rem 2rem;
  text-align: center;
  background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #3b82f6 100%);
  color: #fff;
}
.hero-title {
  font-size: 2.75rem;
  font-weight: 800;
  margin-bottom: 1rem;
  font-family: 'Georgia', 'Times New Roman', serif;
}
.hero-subtitle {
  font-size: 1.2rem;
  opacity: 0.95;
  max-width: 640px;
  margin: 0 auto;
}

/* ── Main Content — wider for business ── */
.main-content {
  flex: 1;
  max-width: 1024px;
  margin: 0 auto;
  padding: 2.5rem 2rem;
  width: 100%;
}
.page-title {
  font-size: 1.75rem;
  margin-bottom: 1.5rem;
  color: var(--template-heading);
  font-weight: 700;
  font-family: 'Georgia', 'Times New Roman', serif;
}

/* ── Page Nav (index links) — button cards ── */
.page-nav ul { list-style: none; display: flex; flex-wrap: wrap; gap: 1rem; }
.page-nav a {
  display: inline-block;
  padding: 0.65rem 1.25rem;
  color: var(--template-text);
  text-decoration: none;
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 8px;
  font-weight: 500;
  transition: background 0.2s, color 0.2s, transform 0.2s;
}
.page-nav a:hover {
  background: var(--brand-primary, var(--template-primary));
  color: #fff;
  transform: translateY(-1px);
  text-decoration: none;
}

/* ── Content (page/post body) ── */
.content { margin-top: 1rem; line-height: 1.7; }
.content p { margin-bottom: 1em; }
.content h1, .content h2, .content h3, .content h4 { margin: 1.5em 0 0.5em; color: var(--template-heading); }
.content img { margin: 1em 0; border-radius: 8px; }
.content ul, .content ol { margin: 0.5em 0 1em 1.5em; list-style: revert; }
.content blockquote {
  border-left: 3px solid var(--brand-primary, var(--template-primary));
  background: #f0f7ff;
  padding: 1em;
  border-radius: 0 6px 6px 0;
  margin: 1em 0;
  color: #374151;
}

/* ── Blog Posts — professional card grid ── */
.posts-list {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.25rem;
}
.posts-list li {
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 10px;
  padding: 1.25rem;
  transition: transform 0.2s, box-shadow 0.2s;
}
.posts-list li:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.posts-list a {
  color: var(--template-heading);
  text-decoration: none;
  font-weight: 600;
  font-size: 1.05rem;
}
.posts-list a:hover { color: var(--brand-primary, var(--template-primary)); text-decoration: none; }

/* ── Events — professional listing with accent border ── */
.events-list { list-style: none; display: grid; gap: 0.75rem; }
.events-list li {
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-left: 4px solid var(--brand-primary, var(--template-primary));
  border-radius: 8px;
  padding: 1.25rem;
}
.events-list li strong {
  display: block;
  color: var(--template-heading);
  font-size: 1.05rem;
  margin-bottom: 0.25rem;
}

/* ── Gallery — clean grid with shadows ── */
.media-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1.25rem;
}
.media-gallery figure {
  margin: 0;
  background: var(--template-surface);
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  border: 1px solid var(--template-border);
}
.media-gallery img {
  width: 100%;
  aspect-ratio: 4/3;
  object-fit: cover;
}
.media-gallery figcaption {
  padding: 0.75rem 1rem;
  font-size: 0.85rem;
  color: #4b5563;
}

/* ── Footer ── */
.site-footer {
  padding: 2rem;
  text-align: center;
  font-size: 0.85rem;
  color: var(--template-muted);
  border-top: 1px solid var(--template-border);
  background: #f3f4f6;
}
.site-footer a { color: var(--template-muted); }

/* ── Responsive ── */
@media (max-width: 768px) {
  .site-header { padding: 0.75rem 1rem; }
  .hero { padding: 3rem 1rem; }
  .hero-title { font-size: 1.85rem; }
  .main-content { padding: 1.5rem 1rem; }
  .page-nav ul { flex-direction: column; }
  .posts-list { grid-template-columns: 1fr; }
  .media-gallery { grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); }
}
"""
