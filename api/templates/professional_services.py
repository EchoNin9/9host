"""
Professional Services template (Task 1.113).

Corporate, case study cards. For consultant/agency sites.
"""

from .base_layout import TemplateRenderer, rich_text_content_css


class ProfessionalServicesRenderer(TemplateRenderer):
    """Corporate style with case study cards and professional typography."""

    def render_css(self) -> str:
        return """
/* Professional Services template — teal corporate, service cards, CTA buttons */
:root {
  --template-primary: #0d9488;
  --template-secondary: #0f766e;
  --template-bg: #f8fafc;
  --template-surface: #ffffff;
  --template-text: #475569;
  --template-heading: #0f172a;
  --template-muted: #94a3b8;
  --template-border: #e2e8f0;
  --template-accent-light: #ccfbf1;
}

/* ── Reset & Body ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 16px; scroll-behavior: smooth; }
body {
  font-family: var(--brand-font, 'Segoe UI', system-ui, -apple-system, sans-serif);
  background: var(--brand-bg, var(--template-bg));
  color: var(--brand-text, var(--template-text));
  line-height: 1.7;
  min-height: 100vh;
}
img { max-width: 100%; height: auto; display: block; }
a { color: var(--brand-primary, var(--template-primary)); text-decoration: none; }
a:hover { text-decoration: underline; }
ul, ol { list-style: none; }

/* ── Site Wrapper ── */
.site-wrapper { min-height: 100vh; display: flex; flex-direction: column; }

/* ── Header — light bar with subtle shadow ── */
.site-header {
  background: var(--template-surface);
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  padding: 0.85rem 2rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}
.site-logo { height: 48px; width: auto; }
.site-title {
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--template-heading);
  letter-spacing: -0.02em;
}
.site-nav ul { display: flex; gap: 0.25rem; list-style: none; flex-wrap: wrap; }
.site-nav a {
  color: var(--template-text);
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  transition: color 0.15s, background 0.15s;
}
.site-nav a:hover {
  color: var(--brand-primary, var(--template-primary));
  background: var(--template-accent-light);
  text-decoration: none;
}

/* ── Hero — corporate with teal gradient ── */
.hero {
  padding: 4.5rem 2rem;
  text-align: center;
  background: linear-gradient(135deg, var(--template-heading) 0%, #1e3a5f 100%);
  color: #fff;
}
.hero-title {
  font-size: 2.75rem;
  font-weight: 700;
  margin-bottom: 0.75rem;
  letter-spacing: -0.02em;
}
.hero-subtitle {
  font-size: 1.15rem;
  color: #cbd5e1;
  max-width: 600px;
  margin: 0 auto;
}

/* ── Main Content ── */
.main-content {
  flex: 1;
  max-width: 60rem;
  margin: 0 auto;
  padding: 2.5rem 2rem;
  width: 100%;
}
.page-title {
  font-size: 1.75rem;
  color: var(--template-heading);
  margin-bottom: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

/* ── Page Nav (index links) — service cards with arrow ── */
.page-nav ul {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
  gap: 1rem;
}
.page-nav li a {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 10px;
  padding: 1.15rem 1.25rem;
  color: var(--template-heading);
  font-weight: 600;
  font-size: 1rem;
  text-decoration: none;
  transition: box-shadow 0.2s, border-color 0.2s, transform 0.15s;
}
.page-nav li a::before {
  content: '\\2192';
  color: var(--brand-primary, var(--template-primary));
  font-size: 1.1rem;
  flex-shrink: 0;
}
.page-nav li a:hover {
  border-color: var(--brand-primary, var(--template-primary));
  box-shadow: 0 4px 12px rgba(13,148,136,0.1);
  transform: translateY(-2px);
  text-decoration: none;
}

/* ── Content — service/case-study prose ── */
.content { margin-top: 1rem; color: var(--template-text); line-height: 1.8; }
.content p { margin-bottom: 1rem; }
.content h1, .content h2, .content h3 {
  color: var(--template-heading);
  margin: 2rem 0 0.65rem;
  font-weight: 600;
}
.content h3 { font-size: 1.2rem; }
.content h4 {
  font-size: 1.05rem;
  color: var(--template-secondary);
  margin: 1.25rem 0 0.5rem;
  font-weight: 600;
}
.content a { color: var(--brand-primary, var(--template-primary)); font-weight: 500; }
.content strong { color: var(--template-heading); }
.content img { margin: 1rem 0; border-radius: 8px; }
.content ul, .content ol { margin: 0.75rem 0 1rem 1.5rem; list-style: revert; }
.content li { margin-bottom: 0.35rem; }
.content blockquote {
  border-left: 4px solid var(--brand-primary, var(--template-primary));
  padding: 1rem 1.5rem;
  margin: 1.25rem 0;
  background: var(--template-accent-light);
  border-radius: 0 8px 8px 0;
  font-size: 1.05rem;
  font-style: italic;
  color: var(--template-secondary);
}

/* ── CTA button style for contact/consult/book links ── */
.content a[href*="contact"],
.content a[href*="consult"],
.content a[href*="book"] {
  display: inline-block;
  background: var(--brand-primary, var(--template-primary));
  color: #fff;
  padding: 0.6rem 1.5rem;
  border-radius: 8px;
  font-weight: 600;
  text-decoration: none;
  transition: background 0.15s;
  margin-top: 0.5rem;
}
.content a[href*="contact"]:hover,
.content a[href*="consult"]:hover,
.content a[href*="book"]:hover {
  background: var(--template-secondary);
  text-decoration: none;
}

/* ── Blog Posts — rounded cards ── */
.posts-list {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(18rem, 1fr));
  gap: 0.85rem;
}
.posts-list li {
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 10px;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.posts-list li:hover {
  border-color: var(--brand-primary, var(--template-primary));
  box-shadow: 0 2px 8px rgba(13,148,136,0.08);
}
.posts-list a {
  display: block;
  padding: 1rem 1.15rem;
  color: var(--template-heading);
  font-weight: 600;
  text-decoration: none;
}
.posts-list a:hover { text-decoration: none; }

/* ── Events ── */
.events-list { list-style: none; display: grid; gap: 0.6rem; }
.events-list li {
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 8px;
  padding: 0.85rem 1.15rem;
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}
.events-list li strong { color: var(--template-heading); font-weight: 600; }

/* ── Gallery — rounded frames ── */
.media-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
  gap: 1rem;
}
.media-gallery figure {
  margin: 0;
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 10px;
  overflow: hidden;
  transition: box-shadow 0.2s;
}
.media-gallery figure:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.06);
}
.media-gallery img { width: 100%; aspect-ratio: 16/10; object-fit: cover; }
.media-gallery figcaption {
  padding: 0.65rem 0.85rem;
  font-size: 0.875rem;
  color: var(--template-text);
}

/* ── Footer — dark corporate ── */
.site-footer {
  background: var(--template-heading);
  color: var(--template-muted);
  padding: 1.5rem 2rem;
  text-align: center;
  font-size: 0.85rem;
}
.site-footer a { color: var(--template-muted); }

/* ── Responsive ── */
@media (max-width: 768px) {
  .site-header { flex-direction: column; align-items: flex-start; padding: 0.75rem 1rem; }
  .hero { padding: 3rem 1rem; }
  .hero-title { font-size: 2rem; }
  .main-content { padding: 1.5rem 1rem; }
  .page-title { font-size: 1.35rem; }
  .page-nav ul { grid-template-columns: 1fr; }
  .posts-list { grid-template-columns: 1fr; }
}
"""
