# T-30 — Admin SPA UX audit

Scope: `frontend/src` (stage.echo9.net / app.echo9.net). Each flow lists the problems found and the fix. **Done** means it shipped in T-30 (frontend only). **Deferred** means it needs an API change or more design work; see the end of this file.

## Cross-cutting (visual system and shell)

| Problem | Fix |
|---|---|
| Stock shadcn neutral theme, system font, no type scale. The only brand mark was a teal "Echo9" text label, unrelated to the landing site (paper, ink, coral, Geist). | **Done.** Tokens in `index.css`: warm paper sidebar, ink text, and coral (`#b83a22` light, `#f0714f` dark) for "current location" and the one primary action. Geist and Geist Mono, mono eyebrow labels, status tokens (success, warning, danger, info) and layered shadows. Light and dark themes checked against AA. |
| Every page built its own header, padding, loading text ("Loading…") and empty card. Spacing and heading sizes drifted between pages (`p-6` on some pages, `TenantPage` on others). | **Done.** `components/page.tsx` adds `Page`, `PageHeader`, `EmptyState`, `LoadingState` (skeleton plus `role=status`), `Notice` and `FormField`. `TenantPageHeader` keeps the h1/h2 embedded rule. |
| Status pills were hand-coloured per page (`bg-green-100 …`), so one state looked different on different pages. | **Done.** `ui/badge.tsx` with tones, plus `TierBadge`, `SiteStatusBadge` and `DomainStatusBadge` in `components/status-badges.tsx`. |
| Native `<select>` elements had six different class strings, and some had no dark background. Module toggles were a hand-built CSS switch. | **Done.** Added `ui/native-select.tsx` and a Radix `ui/switch.tsx`. |
| Destructive actions used `window.confirm` (sites, domains) or a side sheet (users, roles). | **Done.** `components/confirm-dialog.tsx` is used for every delete, rollback and tenant delete. |
| Sheets had no body padding and a fixed 75% width on phones. | **Done.** `ui/sheet.tsx` adds padding, a header rule, full width on phones, and a footer that stacks buttons on phones. |
| Shell: the header showed only the word "Echo9". The sidebar footer was a pile of tiny links (theme, back, sign out). The impersonation notice was 12px text in the footer. On phones, the sidebar stayed open after a link was tapped. | **Done.** `components/app-shell.tsx` adds breadcrumbs in the top bar, nav split into Workspace and Manage groups, a user menu (theme Light/Dark/System, Platform admin, All tenants, Sign out), a full-width impersonation banner, and closes the sidebar on navigation on phones. |
| "← Back to platform" went to `/`, which immediately redirected back to the first tenant (a loop). | **Done.** "All tenants" links to `/?choose=1`, which shows the picker instead of redirecting. |
| Keyboard focus rings were 50% opacity (`ring-ring/50`), low contrast on the paper background. | **Done.** Rings are 2px at 80% plus offset, with a global `:focus-visible` outline for raw buttons and links. |

## Login, signup, confirm, site sign-in, tenant picker

| Problem | Fix |
|---|---|
| Generic centred cards. The sign-in button read "Setting password…" while signing in. | **Done.** Shared `AuthLayout` with the brand mark. The label bug is fixed. |
| `/auth/confirm` opened directly (from an email link or after a reload) had no email, so the confirmation always failed. | **Done.** It asks for the email when the page has no router state. |
| Site sign-in asked for username, password, then site slug. | **Done.** Tenant slug comes first, in mono, with an example. |
| The tenant picker was a row of buttons. "Create tenant" sent the user to `tenants[0]`, not to the new tenant. | **Done.** The picker is a list with name, slug and role. A new tenant opens directly. |

## Overview (tenant dashboard)

| Problem | Fix |
|---|---|
| Three equal cards ("Sites: 3 sites") with no actions and no next step. The title said "Welcome to acme's admin". | **Done.** Header with the tenant name, tier and default address. KPI tiles link to their pages. A list of recent sites with a status badge and an **Edit content** button. A four-step "get your first site live" checklist shows until a site is live. **New site** opens the create sheet (`/sites?new=1`). |

## Sites, publish and rollback

| Problem | Fix |
|---|---|
| **Edit content**, the main task, was hidden in a "…" menu. Cards did not show the live URL. | **Done.** Each card shows an **Edit content** button, the live URL (mono, opens in a new tab), a status badge (`Live · v14` or `Draft`) and a template chip, or a **No template** warning. |
| The "Blank site" template could be chosen, but publishing then failed with "Site has no template_id". | **Done.** The option is renamed "Decide later" and says a template is needed to publish. The editor shows a warning with **Choose template**, and Publish is disabled until a template is set. |
| Publish results were crammed into the header row next to the buttons. The "Last published" strip used a green box that looked like a success message. | **Done.** The header meta shows the URL and the last publish time. Results appear in a `Notice` with **View live site**. |
| No rollback UI, although `POST /sites/{id}/rollback?version=N` exists. | **Done.** A "…" menu offers **Roll back to an earlier version…**: a dialog that takes a version number and calls the existing endpoint (`rollbackSite` in `api.ts`). No API change. |
| The vertical tab rail was 192px wide on phones. | **Done.** The tab rail is horizontal and scrolls on phones, and vertical on desktop. |
| Locked modules (Posts, Events, Media, Branding) showed an empty panel when billing is off. | **Done.** `ModuleLocked` explains why the module is off and links to Modules. With billing on, it shows `UpgradePrompt`. `FeatureGate` is unchanged and receives this as `fallback`. |
| Two coral buttons competed (Publish and Add page). | **Done.** Add, New and Upload buttons inside the editor are outline buttons. |

## Domains

| Problem | Fix |
|---|---|
| A duplicate "Custom domains" h2 under the "Domains" h1. "Check status" and "DNS setup" appeared twice (row and menu). Delete used `confirm()`. | **Done.** One header with **Add domain**. The row holds the status badge, **Check status** (pending only), **DNS records**, and a menu with **Remove** (confirm dialog). |
| A locked tenant with billing off saw a page with only a title. | **Done.** `ModuleLocked` fallback. |

## Users and roles

| Problem | Fix |
|---|---|
| One card per user, with three outline buttons per row. Account users and site-login users were hard to tell apart. Delete confirmation was in a side sheet. | **Done.** One **Members** list with avatars, role, owner and type badges (`account` / `site login`), ghost actions, and confirm dialogs. **Add user** is renamed **Add site user**, with copy saying what that is. |
| Permission checkboxes said "Allow" next to every module. | **Done.** Rows with a labelled `Switch`. |

## Settings, Modules, Analytics

| Problem | Fix |
|---|---|
| Settings duplicated the Modules toggles, which let users tick tier-locked modules that `PATCH /api/tenant` then rejects. | **Done.** Settings shows tenant facts (name, slug, plan, role, owner with **Transfer**) and links to Modules. Billing stays gated by `VITE_ENABLE_BILLING`. |
| Tier-locked module cards were empty when billing is off. Toggles had no accessible label. | **Done.** Cards say which tier includes the module. Each card has a labelled `Switch` and an On/Off state. |
| Analytics charts used `hsl(var(--primary))` on oklch tokens, so they rendered with the wrong colour. Placeholder data was flagged only in a subtitle. | **Done.** Charts use chart tokens, with a quiet grid and themed tooltip. KPI tiles use tabular figures. A "Sample data" notice shows when `placeholder` is true. |

## Superadmin console

| Problem | Fix |
|---|---|
| The dashboard had two KPI cards. | **Done.** Four KPIs (tenants, users, accounts, site logins), a tenants-by-tier bar, and quick links. |
| The tenants list had three buttons per row, including a red Delete. No search. | **Done.** A table with search and tier badge. The tenant name links to Administer. Impersonate and Delete are in a row menu. Delete uses a confirm dialog. |
| Administer tenant: a full-screen "Loading…" inside the shell, a red **Delete tenant** button next to Impersonate, and tabs that did not scroll on phones. | **Done.** In-page loading and not-found states. Delete moved to an overflow menu. Tabs scroll on phones. The Settings tab has a two-column form with module-override switches. |
| Users: bordered boxes nested in bordered boxes. Inline loading took the full screen. | **Done.** Collapsible tenant groups with compact rows and type badges (`account` / `site login`). |
| Templates: icon-only Edit and Delete buttons had no accessible name. | **Done.** A table with tier badges and labelled icon buttons. The create/edit Sheet works as before (deferred to T-31d/T-32b). |
| Edge health: hand-rolled tables. | **Done.** Shared `Table` and `Badge`, with counts in the card titles. |

## Deferred (candidate tickets)

1. **Version history for rollback.** No API lists published versions, so the rollback dialog asks for a number. Add `GET /sites/{id}/versions` (from `published/v*/manifest.json`) and show a list.
2. **Invite account users from the UI.** Members can only be added as site users. Invite by email needs an API.
3. **Unsaved-changes guard in the page and post editors** still uses `window.confirm` inside the sheet's `onOpenChange`. Move it to `ConfirmDialog`.
4. **Template editing and template picking out of side sheets.** T-30 only re-skinned `admin-templates.tsx` (page layout, table, tokens) and left its create/edit `Sheet` working as before. The site form's template picker is also still inside the Sheet. Moving both to full-page routes belongs to **T-31d / T-32b** (see ADR-0003). Those tickets can also tie the sheet labels to their inputs and replace the raw JSON preview.
5. **Pre-existing lint debt** (`react-hooks/set-state-in-effect` in data-loading effects). This is unrelated to the visual pass.
