# ADR-0003: WYSIWYG Page Editing and Template Admin on a Structured Block Model

- **Status:** Proposed
- **Date:** 2026-11-12
- **Deciders:** Adam (owner approval required before any code — `docs/RUNBOOK_POST_CUTOVER.md` §T-31/T-32)
- **Tickets:** `T-31` (tenant WYSIWYG), `T-32` (superadmin template admin; depends on `T-31`'s content model)

---

## Context

### Current content model

All content lives in the single table behind `TenantStore` (`api/tenant_store.py`), under the tenant partition:

| Entity | Key | Content fields (`api/content_handler.py:36-37`) |
|--------|-----|------|
| Page | `PK = TENANT#{slug}`, `SK = SITE#{site_id}#PAGE#{path}` | `path`, `title`, `body` (HTML string), `status` |
| Post | `SK = SITE#{site_id}#POST#{uuid}` | `slug`, `title`, `body` (HTML string), `excerpt`, `featured_image_s3_key`, `status` |
| Event / Media | `SK = SITE#{site_id}#EVENT#…` / `#MEDIA#…` | structured fields, no HTML |
| Platform template | `PK = TENANT#_platform`, `SK = TEMPLATE#{slug}` | `name`, `description`, `tier_required`, `components` |
| Tenant fork | `PK = TENANT#{slug}`, `SK = TEMPLATE#{slug}` | above + `forked_from`, `customizations` (`api/tenant_templates_handler.py`) |

- `body` is the HTML emitted by the existing TipTap v3 editor (`frontend/src/components/ui/rich-text-editor.tsx`, deps in `frontend/package.json`: `@tiptap/react`, `starter-kit`, `extension-link/image/underline` `^3.20.4`). It is stored **unsanitized**: `content_handler.py` does not call the sanitizer; sanitization happens only at render time.
- Site branding (`site.branding`: colors, font, logo) is emitted as CSS custom properties by `branding_styles()` in `api/templates/base_layout.py`, which accepts only `#hex` colors and a strict font regex.

### Current templates

- A template is **Python code**, not data. `api/templates/__init__.py` maps five slugs (`musician-band`, `personal-tech`, `personal-resume`, `professional-services`, `business-generic`) to `TemplateRenderer` subclasses. Each subclass mostly overrides `render_css()`. All HTML structure lives in `TemplateRenderer` (`base_layout.py`): `_chrome()` (head/header/nav/footer), `render_index()` (hero + auto nav list), `render_page()` (`<h2>` title + `<div class="content">{sanitize_html(body)}</div>`), and blog, post, events, gallery, and 404 pages.
- The DynamoDB `components` map that `scripts/seed_templates.py` seeds (CI step "Seed platform templates" in `.github/workflows/dev.yml:119` and `main.yml:118`) lists `pages` and `sections` (`home: [hero, featured, cta]`, …). **No renderer reads it.** It only shows up as metadata in the superadmin UI and in `GET /api/tenant/sites/{id}/preview` (`api/sites_handler.py:177`).
- `SiteCompiler._renderer_for()` (`api/site_compiler.py`) picks the renderer by `forked_from` or `slug`, and falls back to `business-generic`. Tenant `customizations` are stored but never rendered.
- Superadmin template admin (`frontend/src/pages/admin-templates.tsx`, `api/admin_templates_handler.py`) edits only name, description, and tier, and shows `components` as raw `JSON.stringify`. Writes go straight to boto3 (they bypass `TenantStore`), and there is no versioning: a `PUT` overwrites in place.

### Invariants this ADR must preserve

1. **`compile_site(snapshot, mode)` stays pure**: no boto3, clock, or env reads, and the same snapshot yields the same bytes (ADR-0002 §3).
2. **Sanitization**: `api/html_sanitizer.py` uses a stdlib `HTMLParser` allowlist with no `style`, `class`, or `id` attributes, drops `on*` attributes, strips `script/style/iframe/object/embed` together with their contents, blocks `javascript:/vbscript:/data:text/html`, and hardens `target=_blank`.
3. **Root-relative links**: live mode uses `/`, `/about/`, `/blog/`, `/posts/{slug}/`. Draft mode uses the prefix `/preview` (`DRAFT_BASE_PATH`). Today `base_path` is applied only to links the renderer generates. **Links typed inside rich-text bodies are not prefixed in draft**, so in preview they escape to the live site. This is an existing gap.
4. **Draft preview**: `POST …/draft-publish` → `compile_site(mode="draft")` → S3 `draft/`. `GET …/draft-token` (`api/draft_handler.py`) issues an HS256 JWT. `infra/cf-preview-content.js` verifies it at the edge against the KVS key `__preview_jwt_secret__`.
5. **Tenant isolation**: every key starts with `TENANT#` (platform templates use the pseudo-tenant `_platform`).

---

## Options Considered: Editor Library

Facts were checked 2026-11-12 (Puck releases and license: puckeditor.com blog and GitHub; GrapesJS license: GitHub and Snyk). Bundle sizes are approximate min+gzip orders of magnitude. Phase 0 must measure them with `vite build`.

| | **Puck** (`@puckeditor/core`) | **TipTap / ProseMirror** | **Lexical** | **GrapesJS** | **Editor.js** |
|---|---|---|---|---|---|
| Model | Visual **page builder**: drag-drop tree of typed React components with typed props/fields; nested `slot` fields | Rich-text document (ProseMirror nodes/marks) | Rich-text document (Lexical nodes) | Full HTML/CSS canvas builder (component tree + style manager) | Flat list of typed blocks |
| Output | JSON `{root:{props}, content:[{type, props}]}`; we own the render | HTML or ProseMirror JSON | Lexical JSON (HTML via `@lexical/html`) | Project JSON + **arbitrary HTML + CSS** | JSON `{blocks:[{type,data}]}` |
| License | MIT (core). Puck Cloud/AI is a paid add-on and not needed. | MIT (core). Some Pro extensions are paid; not needed. | MIT | BSD-3-Clause (core). Studio SDK is commercial. | Apache-2.0 |
| React 19 | Official since 0.17 (Dec 2024). Current line 0.23 (Aug 2026). | Already running here on React 19.2 | Yes (`@lexical/react`) | Not React. Vanilla JS in its own iframe canvas; needs a wrapper. | Not React. Vanilla JS; only community wrappers. |
| Bundle | Medium (React + dnd); measure | **0 KB incremental**: already shipped | Small core + plugins | Large (heaviest option) | Small core + one plugin per block |
| Layout / sections | **Yes, native** | No (prose only) | No (prose only) | Yes | Vertical stack only, no columns |
| Fit with Python render + sanitizer | **High**: we define every block type and render it in Python | High for prose only | Medium: we must reimplement its node set | **Poor**: emits free-form CSS/inline styles/classes the allowlist strips | Medium: plugin data shapes vary; weak React story |
| Maintenance | Active: 0.21 Jan, 0.22 Jun, 0.23 Aug 2026. Still pre-1.0, so expect API churn. | Very active, 3.x stable | Active (Meta), still 0.x | Active; the vendor's focus is shifting to commercial Studio | Slower cadence; small plugin ecosystem |

### Decision on library

**Puck for page layout (blocks and sections), with our existing TipTap `RichTextEditor` as the custom field inside rich-text blocks.**

Rejected:
- **TipTap alone**: it is what we have today. It cannot express hero, columns, galleries, or CTAs, and those layouts are the substance of "edit pages visually". It stays as the prose editor.
- **Lexical**: same limitation as TipTap, plus a migration away from a library we already ship.
- **GrapesJS**: produces arbitrary HTML/CSS, which defeats the sanitizer allowlist and Python-side rendering. It is a non-React canvas, the heaviest bundle, and its commercial direction is a risk. Any "WYSIWYG that round-trips" claim would rest on storing tenant-authored CSS, which is a stored-XSS and CSS-injection surface.
- **Editor.js**: no layout nesting (no columns), no first-party React, and slow maintenance.

---

## Decision

### 1. Content model: a structured block document, not stored HTML

Pages get a new attribute `doc`. It is a **JSON string** (not a DynamoDB map, which avoids `Decimal` coercion and keeps byte-exact round-trips) holding a versioned block tree:

```json
{
  "schema": 1,
  "root": { "props": { "title": "About", "meta_description": "…" } },
  "content": [
    { "type": "Hero", "props": { "id": "b1", "heading": "We are Acme", "subheading": "…",
        "image": { "media_id": "…" }, "cta": { "label": "Contact", "link": { "kind": "page", "path": "contact" } } } },
    { "type": "Columns", "props": { "id": "b2", "count": 2,
        "col_0": [ { "type": "RichText", "props": { "id": "b3", "html": "<p>…</p>" } } ],
        "col_1": [ { "type": "Image", "props": { "id": "b4", "image": { "media_id": "…" }, "alt": "…" } } ] } }
  ]
}
```

- The shape deliberately matches Puck's `Data` (`root` + `content[]` of `{type, props}`, with slots as arrays in props), so the frontend passes it straight through. **The schema is ours**: `schema` is our version number. A Python validator is the source of truth, and a Puck major-version change becomes a frontend adapter rather than a data migration.
- **Block catalog v1** (`api/blocks/`, mirrored in `frontend/src/editor/blocks/`): `Hero`, `RichText`, `Image`, `Gallery` (explicit media ids or "all site media"), `Columns` (2–3 slots, nesting depth ≤ 3), `CallToAction`, `Divider`, `Spacer`, `PostList` (latest N), `EventList` (upcoming N), `LinkList` (label + link). No forms, no embeds, no free CSS.
- **Prop types are closed**: `text` (plain, escaped at render), `richtext` (HTML, sanitized), `media` (`{media_id}` resolved against `snapshot.media`, never a URL), `link` (`{kind: "page"|"post"|"blog"|"events"|"gallery"|"home", path?}` or `{kind: "external", url}`), `enum` (variant/alignment from a fixed list), `int` (bounded). Unknown block types or props are **rejected on save** and **skipped on compile**.
- **Size cap**: `doc` ≤ 256 KB (DynamoDB item limit is 400 KB). Media lives in S3 and is referenced by id.
- **Posts stay rich text** (`body` HTML through TipTap) in v1. Blog posts are prose, and the post template already provides the chrome. The compiler internally treats `body` as a one-block `RichText` doc so both share one render path.
- **Home page**: a reserved page `path = "_home"` (rejected by `_validate_slug` for user pages) compiled to `index.html`. When absent, `render_index()` keeps today's hero + auto nav list. (See Open Question 2.)

### 2. `compile_site` stays pure: blocks are rendered to HTML in Python

- New pure module `api/blocks/` contains a registry `BLOCKS: dict[str, BlockSpec]`, where each spec has `validate(props) -> props` and `render(props, rctx) -> str`. `RenderContext` is a frozen dataclass built from the snapshot: `base_path`, `media_base`, `tenant_slug`, `site_id`, a `media` index by id, `pages` index by path, `posts`, `events`, and template `tokens`. No I/O.
- `compile_site` builds `main_html = render_doc(page["doc"], rctx)` and passes it to the template. `TemplateRenderer.render_page()` gains a `main_html` path. The renderers keep owning `<head>`, header/nav, footer, CSS, and the blog, events, and gallery list pages. Block markup uses stable BEM-ish classes (`.b-hero`, `.b-columns--2`) that every template's `render_css()` styles, with a shared default in `base_layout.blocks_css()` (same pattern as today's `rich_text_content_css()`).
- Purity tests stay: same snapshot gives a byte-identical bundle, and `api/blocks/` has no `boto3`/`os.environ`/`datetime.now` imports (enforced by an AST test).
- **The editor canvas is a React approximation; the compiled HTML is the truth.** Puck renders our React block components inside an iframe that loads the template's real CSS (served from a `GET …/templates/{slug}/css` endpoint that returns `renderer.render_css() + blocks_css()`). Drift between the React and Python renderers is controlled by **shared golden fixtures**: `tests/fixtures/blocks/*.json` render to `*.html` in pytest, and vitest asserts that the React render's normalized DOM matches. "Preview draft" stays the authoritative WYSIWYG check.

### 3. Sanitization: on save and again on compile

| Where | What |
|-------|------|
| **Save** (`content_handler.py` PUT/POST for pages; new `api/blocks/validate.py`) | Parse `doc`. Reject unknown `schema`, unknown block types, unknown props, depth > 3, or size > 256 KB with `400 {"error", "path": "content[1].props.col_0[0]"}`. Run `richtext` props through `sanitize_html()` and **store the sanitized value**. Check `link.external.url` with `_is_dangerous_url` and require `https:`, `http:`, or `mailto:`. Normalize links to the tenant's own hosts (`https://{site_slug}.echo9.net/x/` or a custom domain) to `{kind:"page"}`. Strip `text` props of control characters. Post `body` also gets sanitize-on-save (closes today's gap). |
| **Compile** (`render_doc`) | Re-validate and re-sanitize every `richtext` prop and HTML-escape every `text` prop (defense in depth for legacy rows, manual DynamoDB edits, and future block versions). Media and links are emitted only from resolved, escaped values. |

- **The allowlist is not widened.** Alignment, width, and variants are block `enum` props rendered to fixed classes by Python, so tenants never author `class`, `style`, or `id`. `iframe` stays stripped. Embeds (YouTube, maps), if wanted, become dedicated provider blocks that take an id, not a URL or HTML (Open Question 7).
- **Root-relative links**: `link` props are rendered by `link_href(link, base_path)`, giving `"" + "/about/"` live and `"/preview/about/"` draft. External links get `rel="noopener noreferrer"` when `target=_blank`. For HTML inside `RichText`, after sanitization a pure `rewrite_internal_hrefs(html, base_path)` prefixes root-relative `href`s (`/…`, not `//…`) with `base_path` in draft mode. This fixes the existing preview escape in invariant 3. The TipTap link dialog gains a "Link to page" picker that inserts root-relative `/path/`.

### 4. Migration: lazy, per-site opt-in, with `body` kept for rollback

- **Read path (lazy, no backfill required)**: a page without `doc` is compiled as `{"content": [{"type": "RichText", "props": {"html": body, "legacy": true}}]}`. The `RichText` block with `legacy: true` **is the raw-HTML block**. It renders `<div class="content">{sanitize_html(rewrite_body_media_urls(body))}</div>` so that **legacy pages compile byte-identically to today** (gated by a golden test over every existing fixture). The editor shows it as one editable rich-text block that the tenant can split into further blocks.
- **Write path**: a page saved from the new editor writes `doc` **and** dual-writes `body = render_doc(doc, live ctx)` (the main column HTML). Old code paths and a rollback therefore still render something correct.
- **Rollout flag**: per-site attribute `site.editor = "blocks" | "richtext"` (default `"richtext"`), plus global kill switch `BLOCK_EDITOR_ENABLED` / `VITE_ENABLE_BLOCK_EDITOR`, the same pattern as `BillingFeatureFlag`. With the flag off, the compiler ignores `doc` and uses `body`.
- **Rollback**: turn the flag off and republish. `body` is current because of the dual-write. No data is deleted, and `doc` stays dormant.
- **Batch backfill** (`scripts/backfill_page_docs.py`, idempotent, `--dry-run`, wired after the seed step in CI like `backfill_gsi4_sites.py`) is **deferred** to the final phase. It only wraps `body` into a `legacy` RichText `doc`, and only runs once all sites are on `blocks`. Lazy wrapping makes it optional. Its value is removing the legacy branch and the dual-write.

### 5. Template schema and superadmin admin (T-32)

A template stays **renderer code + data**. Superadmins author data. They do not author HTML or CSS.

```text
PK = TENANT#_platform  SK = TEMPLATE#{slug}                 -> head: name, description, tier_required,
                                                               base_renderer, latest_version, published_version
PK = TENANT#_platform  SK = TEMPLATE#{slug}#V#{0000n}       -> immutable version: schema, tokens,
                                                               allowed_blocks, page_presets, header, footer
```

- `base_renderer`: one of the registered Python renderers (today's five). It supplies chrome and CSS and is the existing `forked_from` mechanism made explicit.
- `tokens`: `{primary, secondary, bg, text, heading_font, body_font, radius, spacing}`, validated with the same regexes as `branding_styles()` and emitted as `--template-*` custom properties. Site `branding` still overrides them.
- `allowed_blocks`: a subset of the catalog, optionally tier-gated (`{"Columns": "PRO"}`).
- `page_presets`: `{"_home": doc, "about": doc, "contact": doc, …}`. These are block docs (same schema as §1) that seed a site's pages when the template is applied, and they replace the unused `components.pages/sections`. Text in presets is placeholder copy.
- `header` / `footer` slots: limited config (show logo, nav style enum, footer `LinkList` + text), not free blocks.
- **Versioning**: editing creates a draft version `V{n+1}`, and "Publish template" sets `published_version`. Sites store `template_version` when the template is applied. Already-applied pages are tenant data and are never rewritten by template edits. Token and chrome changes reach a site only when the tenant (or a superadmin) chooses "Update to v{n}" and republishes (Open Question 5). Versions are never deleted while a site pins them.
- **Admin UX** (`admin-templates.tsx` → `/admin/templates/:slug/edit`): left panel has metadata, base renderer, tier, and the tokens form (color pickers and font select with a live CSS variable preview). The center is the **same Puck editor and block config as T-31**, editing one preset at a time (page tabs: Home, About, …) inside an iframe using `base_renderer` CSS + tokens. The right panel has the allowed-blocks checklist, the version list with diff summary, and "Preview with sample site". That preview compiles a fixture snapshot through `compile_site(mode="draft")` via a superadmin-only `POST /api/admin/templates/{slug}/preview` and returns HTML for an iframe `srcdoc` (sandboxed, no S3 write).
- `seed_templates.py` migrates each `components` map to `V0001` with presets derived from `components.pages` (one `RichText` placeholder block per section). It stays idempotent.
- Handlers move onto `TenantStore` (`get_template`, `put_template_version`, `list_template_versions`), so no raw boto3 is left in `admin_templates_handler.py`.

### 6. Draft preview flow (unchanged transport)

1. In the editor, "Save draft" sends PUT pages with `doc` (validated and sanitized).
2. "Preview" sends `POST …/draft-publish`. `compile_site(mode="draft")` renders blocks with `base_path="/preview"`, rewrites rich-text internal hrefs to `/preview/…`, and inlines CSS plus the token script (`_DRAFT_TOKEN_SCRIPT` already propagates `?token=` on `/preview` anchors).
3. `GET …/draft-token` returns the URL. `cf-preview-content.js` verifies the HMAC and serves `draft/`. **No edge change is required.** Per the memory note on `cf-site-content.js`, any future edge edit still goes through `aws cloudfront test-function` before deploy.
4. The in-editor canvas is instant feedback only. The Preview button is the round-trip guarantee and is placed in the Puck header.

### 7. Security summary

- **XSS**: no tenant-authored markup reaches output except `richtext` HTML, which is sanitized on save and on compile with the unchanged allowlist. Every other prop is escaped plain text, a closed enum, a bounded int, or a resolved media/link reference. No `style`/`class`/`id`/`iframe`. Template tokens use regex allowlists before reaching `<style>`.
- **Editor-side**: the Puck canvas iframe renders our own React components (React escapes text). `RichText` in the canvas uses `dangerouslySetInnerHTML` **only on server-sanitized HTML**, and the admin preview `srcdoc` iframe uses `sandbox` without `allow-scripts`.
- **Tenant isolation**: `doc` lives on existing `TENANT#{slug}` / `SITE#{id}#PAGE#…` items. Media refs are resolved only against `snapshot.media` (same tenant and site), so a foreign `media_id` renders nothing. Link refs resolve only against the snapshot's pages and posts. Templates read `TENANT#_platform` (shared read-only) or `TENANT#{slug}` forks, and template writes stay `ctx.require_superadmin()` (platform) or `MANAGE_ROLES` (fork).
- **Abuse**: the size cap, depth cap, and block-count cap (≤ 200 blocks per page) bound compile time inside Lambda.

---

## Implementation Plan

Each step is one PR, `agent{N} task T-31x: …`.

| Step | Scope | Tests |
|------|-------|-------|
| **T-31a** spike | Branch-only: add `@puckeditor/core` (pin the exact 0.23.x), render one `RichText` block with our TipTap field on React 19.2, lazy-load the route, record `vite build` chunk sizes. Go/no-go report. | Manual + build size numbers |
| **T-31b** block core | `api/blocks/` (registry, validators, renderers, `link_href`, `rewrite_internal_hrefs`), `render_doc`, legacy wrap, `compile_site` integration behind flag, `blocks_css()` in every template | pytest goldens per block × live/draft; **byte-identical legacy bundle** for all existing compiler fixtures; AST purity test; XSS corpus through every `richtext`/`text`/`link` prop |
| **T-31c** save path | `doc` in `content_handler.py` (validate, sanitize, size cap, dual-write `body`), sanitize-on-save for post `body`, `site.editor` flag, `_home` reserved path | Handler tests with `InMemoryTenantStore`: 400 paths, sanitized-on-store, dual-write, cross-tenant `media_id` ignored |
| **T-31d** editor UI | `frontend/src/editor/` Puck config + React blocks mirroring Python, iframe canvas loading template CSS, page editor route behind `VITE_ENABLE_BLOCK_EDITOR` + `site.editor`, link and media pickers | Vitest: each block renders from golden JSON and the normalized DOM matches the golden HTML; `npm run build` |
| **T-31e** preview + home | Puck header Save/Preview wiring, `_home` editing, rich-text internal-link picker | pytest draft href rewrite; manual preview on stage |
| **T-32a** template data | Version items, `TenantStore` template methods, admin handlers on store, preview endpoint, `seed_templates.py` → `V0001` | pytest: versioning, immutability, token validation, seed idempotency, superadmin-only |
| **T-32b** template admin UI | `/admin/templates/:slug/edit`: tokens form, preset editing with the shared Puck config, allowed blocks, versions, sandboxed preview | Vitest form/token validation; build |
| **T-31f** cleanup | `backfill_page_docs.py` + CI step, flip default to `blocks`, later drop the dual-write and legacy branch | Backfill dry-run test; full suite |

Run all four CLAUDE.md suites on every step. `node --test infra/tests/*.test.mjs` should stay green with no edge changes.

---

## Consequences

- **Positive**: tenants get real layout editing (hero, columns, galleries, CTAs) while the published output stays static, root-relative, sanitized HTML from a pure Python compiler. Superadmins can create templates as data (tokens + presets) without a deploy. Preview links stop escaping to live. Post bodies are sanitized at rest.
- **Negative / trade-offs**:
  - Two renderers per block (React canvas, Python output) need the golden-fixture parity discipline.
  - Puck is pre-1.0, so we pin it, and our own `schema` insulates stored data.
  - New *layouts and CSS* still need a Python renderer and a deploy. Only tokens, presets, and block choice are data.
  - The dual-write `body` doubles page item size until T-31f.

---

## Open Questions for the Owner

1. **Dependency**: is Puck (MIT, pre-1.0, ~monthly releases) acceptable as a pinned dependency, given that T-31a's measured bundle size is the go/no-go gate?
2. **Home page**: should it be a reserved `_home` page doc (recommended), or stay auto-generated (hero + nav list) with optional blocks above it?
3. **Posts**: keep posts as TipTap rich text in v1 (recommended), or move them to blocks too?
4. **Template CSS authoring**: confirm superadmins get tokens + presets only and no raw CSS (recommended). Raw CSS would need its own sanitizer and review.
5. **Template upgrades**: should sites pin `template_version` and upgrade explicitly (recommended), or auto-follow the published version on next publish?
6. **Tenant forks** (`/api/tenant/templates/fork`, Pro+): keep them, and if so should a fork copy tokens and presets into the tenant partition? Today `customizations` is stored but never rendered.
7. **Embeds and forms**: are provider-specific embed blocks (YouTube, maps) or a contact form (needs a backend endpoint plus spam control) in scope for v1?
8. **Tier gating**: should any blocks be Pro+ (for example `Columns`, `Gallery`), enforced through `tier_config.py` and `<FeatureGate>`?
9. **Rollout**: opt-in per site first (recommended), or switch everyone at once? And when should the batch backfill (T-31f) run?

## Owner Answers (2026-11-12)

1. **Puck**: OK as a pinned dependency during bootstrap (T-31a bundle-size gate still applies).
2. **Home page**: reserved `_home` page doc.
3. **Posts**: TipTap rich text in v1 (recommendation accepted).
4. **Template CSS**: confirmed — tokens + presets only, no raw CSS for superadmins.
5. **Template upgrades**: pending owner confirmation of: pin `template_version`; retire by *deprecating* (not selectable for new sites, "update available" banner, no delete while pinned); superadmin bulk "upgrade all sites to vN".
6. **Tenant forks**: pending owner confirmation of: drop forks (per-site token overrides replace them).
7. **Embeds**: in scope for v1 (provider allowlist). Contact form: out.
8. **Tier gating**: yes, some blocks Pro+, but deferred to `T-34`; v1 goal is working templates with no block gating.
9. **Rollout**: all sites at once (all are owner-owned). The per-site opt-in flag stays only as a rollback switch; T-31f backfill runs right after T-31e.
