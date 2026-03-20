"""
Musician/Band template (Task 1.113).

Dark theme, hero image, tour dates grid. For band/artist sites.
"""

from .base_layout import TemplateRenderer, rich_text_content_css


class MusicianBandRenderer(TemplateRenderer):
    """Dark theme with accent colors, sidebar-style nav, tour dates grid."""

    def render_css(self) -> str:
        return """
/* Musician/Band template — dark theme, bold hero, tour dates, gallery focus */
:root {
  --template-primary: #e11d48;
  --template-secondary: #7c3aed;
  --template-bg: #0f0f0f;
  --template-surface: #1a1a1a;
  --template-surface-hover: #252525;
  --template-text: #f5f5f5;
  --template-muted: #a3a3a3;
  --template-border: #333;
}

/* ── Reset & Body ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 16px; scroll-behavior: smooth; }
body {
  font-family: var(--brand-font, 'Helvetica Neue', Helvetica, Arial, sans-serif);
  background: var(--brand-bg, var(--template-bg));
  color: var(--brand-text, var(--template-text));
  line-height: 1.6;
  min-height: 100vh;
}
img { max-width: 100%; height: auto; display: block; }
a { color: var(--brand-primary, var(--template-primary)); text-decoration: none; }
a:hover { text-decoration: underline; }
ul, ol { list-style: none; }

/* ── Site Wrapper (sticky footer) ── */
.site-wrapper { min-height: 100vh; display: flex; flex-direction: column; }

/* ── Header — dark bar with accent underline ── */
.site-header {
  background: #000;
  padding: 0.75rem 2rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
  border-bottom: 2px solid var(--brand-primary, var(--template-primary));
}
.site-logo { height: 48px; width: auto; border-radius: 50%; }
.site-title {
  font-size: 1.3rem;
  font-weight: 700;
  color: #fff;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-family: 'Georgia', serif;
}
.site-nav ul { display: flex; gap: 1.5rem; list-style: none; flex-wrap: wrap; }
.site-nav a {
  color: #aaa;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  transition: color 0.2s;
}
.site-nav a:hover { color: var(--brand-primary, var(--template-primary)); text-decoration: none; }

/* ── Hero — dramatic gradient ── */
.hero {
  padding: 5rem 2rem;
  text-align: center;
  background: linear-gradient(180deg, #000 0%, #1a1a2e 100%);
  color: #fff;
}
.hero-title {
  font-size: 3rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.75rem;
  font-family: 'Georgia', serif;
}
.hero-subtitle {
  font-size: 1.1rem;
  color: #bbb;
  max-width: 600px;
  margin: 0 auto;
}

/* ── Main Content ── */
.main-content {
  flex: 1;
  max-width: 900px;
  margin: 0 auto;
  padding: 2.5rem 2rem;
  width: 100%;
}
.page-title {
  font-size: 2rem;
  margin-bottom: 1.5rem;
  color: var(--brand-primary, var(--template-primary));
  font-family: 'Georgia', serif;
}

/* ── Page Nav (index links) ── */
.page-nav ul { list-style: none; }
.page-nav li {
  border-bottom: 1px solid var(--template-border);
}
.page-nav a {
  display: block;
  padding: 0.75rem 0;
  color: var(--template-text);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s, padding-left 0.2s;
}
.page-nav a:hover {
  color: var(--brand-primary, var(--template-primary));
  padding-left: 0.5rem;
  text-decoration: none;
}

/* ── Content (page/post body) ── */
.content { margin-top: 1rem; color: #ddd; line-height: 1.7; }
.content p { margin-bottom: 1em; }
.content h1, .content h2, .content h3, .content h4 { margin: 1.5em 0 0.5em; color: #fff; }
.content img { margin: 1em 0; border-radius: 6px; }
.content ul, .content ol { margin: 0.5em 0 1em 1.5em; list-style: revert; }
.content blockquote {
  border-left: 3px solid var(--brand-primary, var(--template-primary));
  padding-left: 1em;
  margin: 1em 0;
  color: #aaa;
}

/* ── Blog Posts — card style ── */
.posts-list { list-style: none; display: grid; gap: 1rem; }
.posts-list li {
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 8px;
  padding: 1.25rem;
  transition: box-shadow 0.2s, border-color 0.2s;
}
.posts-list li:hover {
  box-shadow: 0 4px 16px rgba(225,29,72,0.15);
  border-color: var(--brand-primary, var(--template-primary));
}
.posts-list a {
  color: #fff;
  text-decoration: none;
  font-weight: 600;
  font-size: 1.1rem;
}
.posts-list a:hover { color: var(--brand-primary, var(--template-primary)); text-decoration: none; }

/* ── Events — tour dates style ── */
.events-list { list-style: none; display: grid; gap: 0.75rem; }
.events-list li {
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-left: 3px solid var(--brand-primary, var(--template-primary));
  border-radius: 4px;
  padding: 1.25rem;
}
.events-list li strong {
  display: block;
  color: #fff;
  font-size: 1.1rem;
  margin-bottom: 0.25rem;
}

/* ── Gallery — dark frames, square aspect ── */
.media-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem;
}
.media-gallery figure {
  margin: 0;
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 6px;
  overflow: hidden;
}
.media-gallery img {
  width: 100%;
  aspect-ratio: 1/1;
  object-fit: cover;
}
.media-gallery figcaption {
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
  color: #999;
  background: #111;
}

/* ── Footer ── */
.site-footer {
  padding: 1.5rem 2rem;
  text-align: center;
  font-size: 0.85rem;
  color: #555;
  border-top: 1px solid #222;
  background: #0a0a0a;
}
.site-footer a { color: #555; }

/* ── Responsive ── */
@media (max-width: 768px) {
  .site-header { padding: 0.75rem 1rem; }
  .site-title { font-size: 1.1rem; }
  .hero { padding: 3rem 1rem; }
  .hero-title { font-size: 2rem; }
  .main-content { padding: 1.5rem 1rem; }
  .media-gallery { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
}
"""
