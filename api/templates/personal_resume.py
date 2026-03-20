"""
Personal Resume template (Task 1.113).

Single-page feel, timeline, skills bars. For resume/CV sites.
"""

from .base_layout import TemplateRenderer, rich_text_content_css


class PersonalResumeRenderer(TemplateRenderer):
    """Professional resume style with timeline and section dividers."""

    def render_css(self) -> str:
        return """
/* Personal Resume template — print-friendly CV, timeline, skills grid */
:root {
  --template-primary: #2563eb;
  --template-secondary: #0c4a6e;
  --template-bg: #fafafa;
  --template-surface: #ffffff;
  --template-text: #334155;
  --template-heading: #0f172a;
  --template-muted: #64748b;
  --template-border: #e2e8f0;
  --template-accent-light: #dbeafe;
  --template-font-serif: 'Georgia', 'Cambria', 'Times New Roman', serif;
  --template-font-sans: 'Segoe UI', system-ui, -apple-system, sans-serif;
}

/* ── Reset & Body ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 16px; scroll-behavior: smooth; }
body {
  font-family: var(--brand-font, var(--template-font-sans));
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

/* ── Header — clean bar with accent underline ── */
.site-header {
  background: var(--template-surface);
  border-bottom: 2px solid var(--brand-primary, var(--template-primary));
  padding: 1rem 2rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}
.site-logo { height: 44px; width: auto; }
.site-title {
  font-family: var(--template-font-serif);
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--template-heading);
  letter-spacing: -0.01em;
}
.site-nav ul { display: flex; gap: 0.25rem; list-style: none; flex-wrap: wrap; }
.site-nav a {
  color: var(--template-muted);
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  padding: 0.3rem 0.6rem;
  border-radius: 4px;
  transition: color 0.15s, background 0.15s;
}
.site-nav a:hover {
  color: var(--brand-primary, var(--template-primary));
  background: var(--template-accent-light);
  text-decoration: none;
}

/* ── Hero — understated, name-focused ── */
.hero {
  padding: 3.5rem 2rem;
  text-align: center;
  background: var(--template-surface);
  border-bottom: 1px solid var(--template-border);
}
.hero-title {
  font-family: var(--template-font-serif);
  font-size: 2.25rem;
  font-weight: 700;
  color: var(--template-heading);
  margin-bottom: 0.5rem;
}
.hero-subtitle {
  font-size: 1.05rem;
  color: var(--template-muted);
  max-width: 500px;
  margin: 0 auto;
}

/* ── Main Content ── */
.main-content {
  flex: 1;
  max-width: 48rem;
  margin: 0 auto;
  padding: 2.5rem 2rem;
  width: 100%;
}
.page-title {
  font-family: var(--template-font-serif);
  font-size: 1.5rem;
  color: var(--template-heading);
  margin-bottom: 1.25rem;
  padding-bottom: 0.4rem;
  border-bottom: 2px solid var(--brand-primary, var(--template-primary));
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-weight: 700;
}

/* ── Page Nav (index links) — section cards with accent border ── */
.page-nav ul {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: 0.75rem;
}
.page-nav li a {
  display: block;
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-left: 4px solid var(--brand-primary, var(--template-primary));
  border-radius: 4px;
  padding: 0.85rem 1rem;
  color: var(--template-heading);
  font-weight: 600;
  font-size: 0.95rem;
  text-decoration: none;
  transition: box-shadow 0.15s, transform 0.15s;
}
.page-nav li a:hover {
  box-shadow: 0 2px 8px rgba(37,99,235,0.12);
  transform: translateY(-1px);
  text-decoration: none;
}

/* ── Content — timeline-style headings ── */
.content { margin-top: 1rem; color: var(--template-text); line-height: 1.8; }
.content p { margin-bottom: 0.85rem; }
.content h1, .content h2, .content h3 {
  font-family: var(--template-font-serif);
  color: var(--template-heading);
  margin: 1.75rem 0 0.5rem;
}
.content h3 {
  font-size: 1.15rem;
  padding-left: 1rem;
  border-left: 3px solid var(--brand-primary, var(--template-primary));
}
.content h4 {
  font-size: 1rem;
  color: var(--template-muted);
  margin: 1rem 0 0.35rem;
  font-style: italic;
}
.content a { color: var(--brand-primary, var(--template-primary)); text-underline-offset: 2px; }
.content a:hover { text-decoration-thickness: 2px; }
.content strong { color: var(--template-heading); }
.content img { margin: 1rem 0; border-radius: 4px; }
.content ul, .content ol { margin: 0.5rem 0 0.85rem 1.5rem; list-style: revert; }
.content li { margin-bottom: 0.25rem; }
.content blockquote {
  border-left: 3px solid var(--brand-primary, var(--template-primary));
  padding: 0.75rem 1.25rem;
  margin: 1rem 0;
  background: var(--template-accent-light);
  border-radius: 0 6px 6px 0;
  font-style: italic;
  color: var(--template-muted);
}

/* ── Blog Posts ── */
.posts-list { list-style: none; }
.posts-list li {
  margin-bottom: 0.5rem;
}
.posts-list a {
  display: block;
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 4px;
  padding: 0.75rem 1rem;
  color: var(--brand-primary, var(--template-primary));
  font-weight: 500;
  text-decoration: none;
  transition: border-color 0.15s;
}
.posts-list a:hover {
  border-color: var(--brand-primary, var(--template-primary));
  text-decoration: none;
}

/* ── Events — timeline markers ── */
.events-list { list-style: none; }
.events-list li {
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-left: 4px solid var(--brand-primary, var(--template-primary));
  border-radius: 4px;
  padding: 0.75rem 1rem;
  margin-bottom: 0.5rem;
}
.events-list li strong { color: var(--template-heading); }

/* ── Gallery ── */
.media-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
  gap: 0.75rem;
}
.media-gallery figure {
  margin: 0;
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 4px;
  overflow: hidden;
}
.media-gallery img { width: 100%; aspect-ratio: 4/3; object-fit: cover; }
.media-gallery figcaption {
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
  color: var(--template-muted);
}

/* ── Footer ── */
.site-footer {
  border-top: 1px solid var(--template-border);
  padding: 1.25rem 2rem;
  text-align: center;
  font-size: 0.8rem;
  color: var(--template-muted);
  background: var(--template-surface);
}

/* ── Print Styles ── */
@media print {
  .site-nav, .site-footer { display: none; }
  .site-header { border-bottom: 2px solid #000; position: static; }
  .hero { display: none; }
  body { background: #fff; color: #000; font-size: 11pt; }
  .main-content { padding: 0; max-width: none; }
  .page-title { border-color: #000; font-size: 13pt; }
  .content h3 { border-color: #000; }
  a { color: #000; }
  .page-nav li a, .posts-list a, .events-list li, .media-gallery figure {
    border-color: #999;
    box-shadow: none;
  }
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .site-header { flex-direction: column; align-items: flex-start; padding: 0.75rem 1rem; }
  .hero { padding: 2rem 1rem; }
  .hero-title { font-size: 1.75rem; }
  .main-content { padding: 1.5rem 1rem; }
  .page-nav ul { grid-template-columns: 1fr; }
}
"""
