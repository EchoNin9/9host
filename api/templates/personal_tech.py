"""
Personal Tech template (Task 1.113).

Clean, code-friendly, project cards. For developer/tech portfolios.
"""

from .base_layout import TemplateRenderer, rich_text_content_css


class PersonalTechRenderer(TemplateRenderer):
    """Light theme, monospace accents, clean typography."""

    def render_css(self) -> str:
        return """
/* Personal Tech template — dark IDE theme, monospace accents, project cards */
:root {
  --template-primary: #58a6ff;
  --template-secondary: #3fb950;
  --template-bg: #0e1117;
  --template-surface: #161b22;
  --template-surface-hover: #1c2128;
  --template-text: #c9d1d9;
  --template-muted: #8b949e;
  --template-border: #30363d;
  --template-mono: 'SF Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
}

/* ── Reset & Body ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 16px; scroll-behavior: smooth; }
body {
  font-family: var(--brand-font, 'Segoe UI', system-ui, -apple-system, sans-serif);
  background: var(--brand-bg, var(--template-bg));
  color: var(--brand-text, var(--template-text));
  line-height: 1.65;
  min-height: 100vh;
}
img { max-width: 100%; height: auto; display: block; }
a { color: var(--brand-primary, var(--template-primary)); text-decoration: none; }
a:hover { text-decoration: underline; }
ul, ol { list-style: none; }

/* ── Site Wrapper (sticky footer) ── */
.site-wrapper { min-height: 100vh; display: flex; flex-direction: column; }

/* ── Header — dark bar with subtle border ── */
.site-header {
  background: var(--template-surface);
  border-bottom: 1px solid var(--template-border);
  padding: 0.75rem 2rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}
.site-logo { height: 36px; width: auto; border-radius: 4px; }
.site-title {
  font-family: var(--template-mono);
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--brand-primary, var(--template-primary));
  white-space: nowrap;
}
.site-title::before { content: '> '; opacity: 0.5; }
.site-nav ul { display: flex; gap: 0.5rem; list-style: none; flex-wrap: wrap; }
.site-nav a {
  color: var(--template-muted);
  text-decoration: none;
  font-family: var(--template-mono);
  font-size: 0.85rem;
  padding: 0.35rem 0.65rem;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}
.site-nav a:hover {
  background: var(--template-border);
  color: var(--brand-primary, var(--template-primary));
  text-decoration: none;
}

/* ── Hero — terminal prompt feel ── */
.hero {
  padding: 4rem 2rem;
  text-align: center;
  background: linear-gradient(180deg, var(--template-surface) 0%, var(--template-bg) 100%);
  border-bottom: 1px solid var(--template-border);
}
.hero-title {
  font-family: var(--template-mono);
  font-size: 2.5rem;
  font-weight: 700;
  color: #e6edf3;
  margin-bottom: 0.75rem;
}
.hero-subtitle {
  font-family: var(--template-mono);
  font-size: 1rem;
  color: var(--template-muted);
  max-width: 600px;
  margin: 0 auto;
}
.hero-subtitle::before { content: '// '; opacity: 0.5; color: var(--template-secondary); }

/* ── Main Content ── */
.main-content {
  flex: 1;
  max-width: 52rem;
  margin: 0 auto;
  padding: 2.5rem 1.5rem;
  width: 100%;
}
.page-title {
  font-family: var(--template-mono);
  font-size: 1.6rem;
  color: #e6edf3;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid var(--template-border);
  padding-bottom: 0.5rem;
  font-weight: 600;
}
.page-title::before {
  content: '## ';
  color: var(--brand-primary, var(--template-primary));
  opacity: 0.6;
}

/* ── Page Nav (index links) — project card grid ── */
.page-nav ul {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
  gap: 0.75rem;
}
.page-nav li a {
  display: block;
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  color: var(--template-text);
  font-family: var(--template-mono);
  font-size: 0.95rem;
  text-decoration: none;
  transition: border-color 0.15s, transform 0.15s;
}
.page-nav li a::before { content: '~/'; color: var(--brand-primary, var(--template-primary)); opacity: 0.6; }
.page-nav li a:hover {
  border-color: var(--brand-primary, var(--template-primary));
  transform: translateY(-2px);
  text-decoration: none;
}

/* ── Content (page/post body) ── */
.content { margin-top: 1rem; color: var(--template-text); line-height: 1.75; }
.content p { margin-bottom: 1rem; }
.content h1, .content h2, .content h3, .content h4 {
  color: #e6edf3;
  margin: 1.5rem 0 0.5rem;
  font-family: var(--template-mono);
}
.content a { color: var(--brand-primary, var(--template-primary)); border-bottom: 1px dashed var(--brand-primary, var(--template-primary)); }
.content a:hover { border-bottom-style: solid; text-decoration: none; }
.content code {
  font-family: var(--template-mono);
  background: var(--template-surface-hover);
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  font-size: 0.9em;
  color: var(--template-secondary);
}
.content pre {
  background: var(--template-surface-hover);
  border: 1px solid var(--template-border);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  overflow-x: auto;
  margin: 1rem 0;
  font-family: var(--template-mono);
  font-size: 0.875rem;
  line-height: 1.5;
}
.content pre code { background: none; padding: 0; color: var(--template-text); }
.content img { margin: 1rem 0; border-radius: 6px; border: 1px solid var(--template-border); }
.content ul, .content ol { margin: 0.75rem 0 0.75rem 1.5rem; list-style: revert; }
.content li { margin-bottom: 0.35rem; }
.content blockquote {
  border-left: 3px solid var(--brand-primary, var(--template-primary));
  padding: 0.5rem 1rem;
  margin: 1rem 0;
  background: var(--template-surface-hover);
  border-radius: 0 6px 6px 0;
  color: var(--template-muted);
}

/* ── Blog Posts — card grid ── */
.posts-list {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(20rem, 1fr));
  gap: 0.75rem;
}
.posts-list li {
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 8px;
  transition: border-color 0.15s, box-shadow 0.2s;
}
.posts-list li:hover {
  border-color: var(--brand-primary, var(--template-primary));
  box-shadow: 0 4px 16px rgba(88,166,255,0.08);
}
.posts-list a {
  display: block;
  padding: 1rem 1.25rem;
  color: var(--brand-primary, var(--template-primary));
  text-decoration: none;
  font-family: var(--template-mono);
  font-weight: 500;
}
.posts-list a:hover { text-decoration: none; }

/* ── Events ── */
.events-list { list-style: none; display: grid; gap: 0.5rem; }
.events-list li {
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 8px;
  padding: 0.85rem 1.15rem;
}
.events-list li strong { color: #e6edf3; }

/* ── Gallery — dark frames ── */
.media-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
  gap: 1rem;
}
.media-gallery figure {
  margin: 0;
  background: var(--template-surface);
  border: 1px solid var(--template-border);
  border-radius: 8px;
  overflow: hidden;
}
.media-gallery img { width: 100%; aspect-ratio: 4/3; object-fit: cover; }
.media-gallery figcaption {
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
  color: var(--template-muted);
  font-family: var(--template-mono);
}

/* ── Footer ── */
.site-footer {
  border-top: 1px solid var(--template-border);
  padding: 1.25rem 1.5rem;
  text-align: center;
  font-size: 0.8rem;
  color: var(--template-muted);
  font-family: var(--template-mono);
  background: var(--template-surface);
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .site-header { padding: 0.75rem 1rem; flex-direction: column; align-items: flex-start; }
  .site-title { font-size: 1rem; }
  .hero { padding: 2.5rem 1rem; }
  .hero-title { font-size: 1.75rem; }
  .main-content { padding: 1.5rem 1rem; }
  .page-nav ul { grid-template-columns: 1fr; }
  .posts-list { grid-template-columns: 1fr; }
  .media-gallery { grid-template-columns: repeat(auto-fill, minmax(10rem, 1fr)); }
}
"""
