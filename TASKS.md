# 9host — Multi-Tenant Website Hosting Platform

> **Branch strategy:** `main` = prod (prod.echo9.net) | `develop` = dev (stage.echo9.net)  
> **Agent roles:** agent1 (backend/infra) | agent2 (frontend/ui) | agent3 (payments)  
> **AWS naming:** All AWS resources MUST use prefix `9host` (e.g. 9host-main, 9host-api, 9host-user-pool, 9host-media)  
> **Agent workflow:** Update task status (TODO → DONE) in this file when completing work.  
> **Parallel work:** See [docs/ORCHESTRATION.md](docs/ORCHESTRATION.md) for branch strategy, tofu state rules, and 3–4 task batches per session. [docs/BATCH_JOBS.md](docs/BATCH_JOBS.md) lists concurrent agent1/agent2 batches.

---

## Active Tasks by Agent

### Agent 1 — Backend / Infra

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 1.0 | Create SSL certificates (ACM for stage/prod) | DONE | Certs validated. GitHub repo vars added. |
| 1.1 | Analyze orangewhip schema (User, Profile) and design Tenant model for DynamoDB | DONE | docs/SCHEMA.md. Tenant, User, Site, Domain entities. |
| 1.2 | Extend DynamoDB single-table: TENANT#{slug}, TENANT#{slug}#USER#{sub}#PROFILE, etc. | DONE | infra/dynamodb.tf. Table 9host-main with pk/sk. |
| 1.3 | Implement middleware: extract `tenant_slug` from URL (e.g. `{tenant}.echo9.net`) and inject into Lambda context | DONE | api/middleware.py, api/handler_example.py. |
| 1.4 | Add GSIs for tenant-scoped queries (byTenant, byTenantEntity, etc.) | DONE | byUser, byDomain in dynamodb.tf. See docs/SCHEMA.md. |
| 1.5 | Set up CI/CD: push to `develop` → stage.echo9.net, merge to `main` → prod.echo9.net | DONE | Workflows pass vars. develop→staging, main→prod. |
| 1.6 | Integrate Roborev post-commit hooks for PR reviews | DONE | `roborev init` — post-commit hook installed, repo registered. |
| 1.7 | OpenTofu remote state: create state bucket + lock table, deploy, configure local + CI/CD | DONE | infra/bootstrap/, scripts/init-backend.sh, docs/BACKEND.md. CI uses backend-config. |
| 1.8 | CloudFront + S3: distribution for stage/prod.echo9.net, S3 origin for frontend build | DONE | 9host-frontend-staging, 9host-frontend-production. OAC, BucketOwnerEnforced. CI: -refresh=false workaround for GetBucketAcl. CNAMEs in CloudNS. |
| 1.9 | Cognito User Pool (9host-user-pool) for auth | DONE | 9host-user-pool, app client 9host-frontend, groups admin/manager/editor/member. |
| 1.10 | API Gateway + Lambda: wire api/ handlers, deploy via CI | DONE | 9host-api. HTTP API + Lambda proxy. /api/health, /api/tenant. |
| 1.11 | Wire CloudNS via API: add provider (ClouDNS/cloudns), auth-id + password vars, echo9.net zone | DONE | infra/cloudns/ standalone config. Credentials in Secrets Manager. manage_records for zone-only mode. docs/CLOUDNS.md. |
| 1.12 | Add required DNS records in CloudNS (OpenTofu): ACM validation CNAMEs, stage/prod CNAMEs → CloudFront | DONE | infra/cloudns/ reads remote state, creates CNAMEs. Use manage_records=false when records exist (provider priority-field import bug). |
| 1.13 | Add echo9.ca for stage/prod: refactor domain→domains list, ACM SANs, CloudFront aliases | DONE | domains = [echo9.net, echo9.ca]. Same S3/CloudFront; 4 hostnames total. |
| 1.14 | Extend CloudNS (1.11–1.12) for echo9.ca zone: CNAMEs for stage/prod, ACM validation | DONE | Zones per domain, ACM validation + stage/prod CNAMEs per zone. |
| 1.15 | Add GET /api/tenants endpoint (user's tenants via GSI byUser, Cognito auth) | DONE | api/tenants_handler.py, auth_helpers.py. Unblocks 2.7. |
| 1.16 | Add GET /api/tenant/analytics placeholder (Pro+ tier, tenant-scoped) | DONE | api/analytics_handler.py. Cognito auth, tenant membership, tier check. Unblocks 2.8. |
| 1.17 | Add Sites API: GET/POST/PUT/DELETE /api/tenant/sites | DONE | api/sites_handler.py. Tenant-scoped CRUD, Cognito auth, tenant membership. Unblocks Sites sidebar UI. |
| 1.18 | Add Domains API: GET/POST/DELETE /api/tenant/domains | DONE | api/domains_handler.py. Pro+ tier, tenant membership, GSI byDomain. Unblocks Domains sidebar UI. |
| 1.19 | Add Stripe webhook route: POST /api/webhooks/stripe | DONE | stripe_webhook_handler.py stub. Unblocks 3.3. |
| 1.20 | Migrate single-user schema to multi-tenant (data migration) | DONE | docs/MIGRATION.md, scripts/migrate_orangewhip_to_9host.py. No-op if no legacy data. |
| 1.21 | Add superadmin Cognito group + auth check | DONE | Cognito group superadmin, auth_helpers.is_superadmin(sub). Platform-level vendor/owner. |
| 1.22 | Add superadmin API routes (list all tenants, get any tenant) | DONE | GET /api/admin/tenants, GET /api/admin/tenants/{slug}. Requires superadmin. |
| 1.23 | Add impersonation (X-Impersonate-Tenant for superadmin) | DONE | Superadmin can set X-Impersonate-Tenant to act as any tenant. Middleware override. |
| 1.24 | Enforce role checks in API (tenantadmin vs tenantuser) | DONE | require_tenant_admin_or_manager in sites/domains. admin/manager for POST/PUT/DELETE. |
| 1.25 | Add module permissions entity + API | DONE | USER#{sub}#PERMISSIONS, GET/PUT /api/tenant/users/{sub}/permissions. |
| 1.26 | Add account owner (owner_sub on tenant) | DONE | owner_sub on tenant, GET /api/tenant returns it. Migration sets first user. |
| 1.27 | Add GET /api/tenant/users (list tenant users) | DONE | users_handler.py, admin/manager only. Unblocks 2.14. |
| 1.28 | Add tenant module_overrides + resolved features in GET /api/tenant | DONE | module_overrides map on tenant. resolved_features in response. |
| 1.29 | Add PATCH /api/admin/tenants/{slug} (superadmin: tier, name, module_overrides) | DONE | Friends & family: set tier without Stripe. Superadmin only. |
| 1.30 | Add site template entity + GET /api/templates (tier-filtered) | DONE | Platform templates. PK=TENANT#_platform, SK=TEMPLATE#{slug}. tier_required per template. |
| 1.31 | Add superadmin templates CRUD: GET/POST/PUT/DELETE /api/admin/templates | DONE | Add/remove templates. Same backend components, different configs. |
| 1.32 | Add template_id to Site, validate on POST /api/tenant/sites | DONE | Site created from template. Check tenant tier >= template.tier_required. |
| 1.33 | Seed templates: musician-band, personal-tech, personal-resume, professional-services, business-generic | DONE | scripts/seed_templates.py. CI runs after tofu apply. |
| 1.34 | Add POST /api/admin/tenants endpoint to create a new tenant | DONE | Superadmin only. Accepts slug (max 60 char), name, tier. Validates slug uniqueness. Creates Tenant, User, and membership records. |
| 1.35 | **FIX: handler.py import shadowing — `patch_tenant_handler` overwritten** | DONE | Import alias `admin_patch_tenant_handler` for admin PATCH route. |
| 1.36 | Superadmin: DELETE /api/admin/tenants/{slug} (delete tenant + cascade) | DONE | Cascade-delete all tenant sub-resources (sites, domains, users, memberships, settings). |
| 1.37 | Superadmin: CRUD /api/admin/tenants/{slug}/domains | DONE | Admin-scoped domain management for any tenant, bypasses membership/tier checks. |
| 1.38 | Superadmin: CRUD /api/admin/tenants/{slug}/sites | DONE | Admin-scoped site management for any tenant, bypasses membership. |
| 1.39 | Superadmin: CRUD /api/admin/tenants/{slug}/users | DONE | Add/remove/role-change users in any tenant. DynamoDB profile + permissions. |
| 1.40 | Superadmin: PUT /api/admin/tenants/{slug}/settings | DONE | Update any tenant settings (module_overrides, owner, etc.) via admin API. |
| 1.41 | CI: add path filters to GHA workflows to skip builds on docs/config-only changes | DONE | Add `paths-ignore` to dev.yml/main.yml for TASKS.md, AGENTS.md, .cursor/**, *.md docs, etc. Avoid unnecessary builds on non-code pushes. |

### Agent 2 — Frontend / UI

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 2.0 | Scaffold Shadcn/UI (components.json, base components) | DONE | frontend/ with Vite, Tailwind v4, Shadcn new-york. Button, Card, Sidebar. |
| 2.1 | Design Tenant Admin Sidebar | DONE | tenant-admin-sidebar.tsx, tenant-admin-layout.tsx; Dashboard, Sites, Domains, Settings |
| 2.2 | Create FeatureFlag utility (Free, Pro, Business tiers) | DONE | lib/feature-flags.ts, tier-context, tier-provider, use-tier |
| 2.3 | Create HOC `withFeatureGate` to wrap restricted UI elements | DONE | FeatureGate component, hocs/with-feature-gate.tsx |
| 2.4 | Implement tenant context provider (tenant_slug from URL) | DONE | contexts/tenant-context.ts, tenant-provider.tsx; hooks/use-tenant.ts |
| 2.5 | Migrate single-user UI to multi-tenant (tenant switcher, routing) | DONE | TenantSwitcher in sidebar, getSwitchTenantUrl, Landing tenant links |
| 2.6 | Auth UI: login/signup with Cognito | DONE | Custom Shadcn forms, Amplify Auth, AuthProvider, /login, /signup, /auth/confirm |
| 2.6a | CI: pass VITE_COGNITO_* vars to frontend build | DONE | dev.yml, main.yml. Add vars in repo Settings → Actions. |
| 2.7 | Tenant list from API: replace getDemoTenants() with /api/tenants | DONE | useTenants hook, fetchTenants API client, Amplify config. CI: VITE_API_URL from tofu output. |
| 2.8 | Advanced Analytics UI (FeatureGate advanced_analytics) | DONE | TenantAnalytics page, Recharts, FeatureGate, /api/tenant/analytics. |
| 2.9 | Sites UI: connect TenantSites to /api/tenant/sites | DONE | List, create, edit, delete. useSites hook, Sheet forms. |
| 2.10 | Domains UI: connect TenantDomains to /api/tenant/domains | DONE | List, add, remove. useDomains hook, site selector, FeatureGate. |
| 2.11 | Add Sign in link to Landing page (when unauthenticated) | DONE | Link to /login when !isAuthenticated. useAuth hook. |
| 2.12 | Add auth routes: /login, /signup, /auth/confirm (wire to Cognito) | DONE | Login, Signup, AuthConfirm pages. Amplify signIn, signUp, confirmSignUp. |
| 2.13 | Superadmin UI: all tenants list, impersonate tenant | DONE | /admin page, ImpersonationContext, X-Impersonate-Tenant in API client. Stop impersonating in sidebar. |
| 2.14 | Tenantadmin UI: users list, role management | DONE | TenantUsers page, /users route, useTenantUsers. Admin/manager only. |
| 2.15 | Module access UI: tenantadmin configures per-user permissions | DONE | Permissions sheet per user, GET/PUT /api/tenant/users/{sub}/permissions. |
| 2.16 | Role-based UI: hide create/edit/delete for tenantuser in Sites, Domains, Settings | DONE | useTenantRole hook, canEdit for admin/manager. editor/member see view-only. |
| 2.17 | Tenant Settings: show owner, transfer owner (if owner) | DONE | useTenantMetadata, owner display, PUT /api/tenant transfer. |
| 2.18 | Use resolved features from GET /api/tenant in FeatureGate | DONE | TenantTierProvider, TierContext.resolved_features, useFeatureGate checks it first. |
| 2.19 | Superadmin: edit tenant (tier, name, module_overrides) | DONE | Edit sheet on Superadmin page. PATCH /api/admin/tenants/{slug}. |
| 2.20 | Site creation: template selector | DONE | Depends on 1.30, 1.32. Fetch GET /api/templates, picker in Add site flow. template_id in POST. |
| 2.21 | Superadmin: templates management UI | DONE | /admin/templates. List, add, edit, delete. GET/POST/PUT/DELETE /api/admin/templates. |
| 2.22 | Tenant Settings: module_overrides editor | DONE | PATCH /api/tenant. Toggles for custom_domains, advanced_analytics. admin/manager only. |
| 2.23 | Site detail: show template used | DONE | Depends on 1.32. Display which template site was created from on site cards/detail. |
| 2.24 | Billing / upgrade UI | TODO | Depends on 3.1, 3.2. Pricing page, upgrade/downgrade buttons, tier badge. |
| 2.25 | Stripe checkout flow | TODO | Depends on 3.1. Checkout page or redirect for subscription. |
| 2.26 | Create Tenant UI (Superadmin) | DONE | Add `createAdminTenant` to `api.ts`, "Add Tenant" button + form on superadmin tenants page. Wire to `POST /api/admin/tenants`. Fields: slug (max 60 chars), display name, tier selector. |
| 2.27 | Add Sign Out button | DONE | Add logout button at the bottom of the left navbar (`tenant-admin-sidebar.tsx`). |
| 2.28 | Post-login navigation (Superadmin) | DONE | Redirect superadmin to `/admin` after successful login. |
| 2.29 | Post-login navigation (Tenant User) | DONE | Redirect tenant admin/user to their tenant dashboard (`/{tenantSlug}`) after successful login. |
| 2.30 | Superadmin Portal: Dashboard | DONE | Main dashboard view for superadmins (landing page after auth). |
| 2.31 | Superadmin Portal: Tenants Section | DONE | List all tenants with clickable links to administer each specific tenant. |
| 2.32 | Superadmin Portal: Administer Tenant | DONE | Dedicated view for superadmins to manage a specific tenant's domains, sites, and users. |
| 2.33 | **FIX: Merge route trees to eliminate hasTenant race condition** | DONE | `AppRoutes` conditionally renders two `<Routes>` trees based on `hasTenant` from TenantContext. Because `TenantLocationSync` updates context in `useEffect` (after render), `hasTenant` is stale during the first render after navigation. This causes: (a) tenant user post-login redirect to `/{slug}` caught by platform catch-all → redirect back to `/`, (b) superadmin impersonation `navigate("/{slug}")` similarly fails, (c) "Back to platform" from tenant → `TenantRootRedirect` sends user back to `/{slug}`, (d) "Platform admin" from tenant → `/:tenantSlug` captures `admin` as a slug. **Fix:** merge all routes into one `<Routes>` tree — React Router v6 matches static routes (`/admin`, `/login`) before dynamic (`/:tenantSlug`). Remove conditional `hasTenant` branching and `TenantLocationSync`. |
| 2.34 | **FIX: Hide "Platform admin" link for non-superadmin users** | DONE | Landing page and tenant sidebar show "Platform admin" only when isSuperadmin. |
| 2.35 | Superadmin: delete tenant UI with confirmation | TODO | Depends on 1.36. Delete button + cascade warning on admin tenant view. |
| 2.36 | Superadmin: manage tenant domains UI (admin-scoped) | TODO | Depends on 1.37. Add/remove domains via /api/admin/tenants/{slug}/domains in administer-tenant view. |
| 2.37 | Superadmin: manage tenant sites UI (admin-scoped) | TODO | Depends on 1.38. Full CRUD for sites via admin API in administer-tenant view. |
| 2.38 | Superadmin: manage tenant users UI (admin-scoped) | TODO | Depends on 1.39. Add/remove/role-change users via admin API. |
| 2.39 | Superadmin: manage tenant settings UI (admin-scoped) | TODO | Depends on 1.40. Edit all tenant settings via admin API. |
| 2.40 | Superadmin: templates management UI enhancements | TODO | Extends 2.21. Improve create/modify/delete templates UX (preview, validation, ordering). |

### Agent 4 — Self-Serve (Future)

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 4.1 | Self-serve tenant signup flow | TODO | Allow regular authenticated users to create their own tenants. |

### Agent 3 — Payments

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 3.1 | Integrate Stripe for tier subscriptions (Free, Pro, Business) | TODO | |
| 3.2 | Map Stripe subscription status → FeatureFlag tier | TODO | |
| 3.3 | Implement upgrade/downgrade flows and webhooks | TODO | |

---

## Save Points

> **Use when pausing work.** Document where you stopped and what to do next.

### Next Task Batches (2026-03-11)

| Batch | Agent 1 (Backend) | Agent 2 (Frontend) | Agent 3 (Payments) | Concurrency |
|-------|-------------------|--------------------|--------------------|----|
| **1** | 1.41 CI path filters | 2.34 Hide "Platform admin" for non-superadmin | — | agent1 + agent2 **concurrent** |
|       |                   | 2.26 Create Tenant UI (superadmin) |   |   |
| **2** | 1.36 DELETE tenant + cascade | 2.40 Templates UI enhancements | — | agent1 + agent2 **concurrent** |
|       | 1.37 Admin domains CRUD |   |   |   |
|       | 1.38 Admin sites CRUD |   |   |   |
|       | 1.39 Admin users CRUD |   |   |   |
|       | 1.40 Admin settings PUT |   |   |   |
| **3** | — | 2.35 Delete tenant UI (← 1.36) | 3.1 Stripe integration | agent2 + agent3 **concurrent** |
|       |   | 2.36 Tenant domains UI (← 1.37) | | |
|       |   | 2.37 Tenant sites UI (← 1.38) | | |
|       |   | 2.38 Tenant users UI (← 1.39) | | |
|       |   | 2.39 Tenant settings UI (← 1.40) | | |
| **4** | — | 2.24 Billing / upgrade UI (← 3.1, 3.2) | 3.2 Map Stripe → tier | agent2 + agent3 **concurrent** |
|       |   | 2.25 Stripe checkout flow (← 3.1) | 3.3 Upgrade/downgrade webhooks | |
| **5** | — | — | — | future |
|       |   | 4.1 Self-serve tenant signup |   | |

> **Arrows (←)** = depends on. Batches are sequential; agents within a batch run concurrently.

---

### Save Point: Navigation & CRUD bugfixes (2026-03-11)

**Status:** Critical bugs identified blocking core workflows: (1) routing race condition in `AppRoutes` prevents cross-boundary navigation (platform ↔ tenant), (2) `handler.py` import shadowing breaks `PATCH /api/admin/tenants/{slug}`, (3) Create Tenant UI (2.26) still TODO, (4) "Platform admin" link visible to non-superadmins.

**Blocking:** Sites, domains, post-login redirect, superadmin impersonation, and tenant creation all broken or missing due to these bugs.

**Next (priority order):**
1. **1.35** — Fix handler.py import alias (agent1, 5 min)
2. **2.33** — Merge route trees to fix navigation (agent2, core fix)
3. **2.26** — Create Tenant UI for superadmin (agent2)
4. **2.34** — Hide "Platform admin" link for non-superadmins (agent2, minor)

### ~~Save Point: Superadmin Portal & Post-Login Routing (2026-03-11)~~ Superseded

**Status:** agent2 tasks 2.20, 2.23, 2.27, 2.28, 2.29, 2.30, 2.31, 2.32 complete. Superadmin portal is built (`/admin`, `/admin/tenants`, `/admin/templates`), post-login routing correctly directs superadmins to `/admin` and single-tenant users to `/:tenantSlug`. Site template selection integrated into site creation.

**Next:** agent3 Stripe integration (3.1–3.3) and agent2 billing UI (2.24–2.25), or agent2 Create Tenant UI for Superadmin (2.26).

### ~~Save Point: Templates backend complete (2026-03-11)~~ Superseded

**Status:** agent1 tasks 1.0–1.33 complete (module_overrides, resolved_features, PATCH admin tenants, templates CRUD, template_id on sites, seed templates in CI). agent2 tasks 2.0–2.19, 2.21, 2.22 done (resolved features, superadmin edit tenant, templates UI, module_overrides editor).

**Next:** agent2 tasks 2.20 (template selector in Add site flow), 2.23 (show template on site cards/detail). Then agent3 Stripe (3.1–3.3) and 2.24–2.25 billing UI.

### ~~Save Point: Batch 1 complete (Phase 2)~~ Superseded

### ~~Save Point: SSL certificates created (Phase 1)~~ ✅ Complete

**Status:** SSL certs validated. GitHub repo vars added. Tasks 1.0–1.24, 2.0–2.13 complete.

---

## Schema Reference (from orangewhip.surf)

9host uses **DynamoDB single-table design** like orangewhip, extended for multi-tenancy:

| Orangewhip (single-tenant) | 9host (multi-tenant) |
|---------------------------|----------------------|
| `USER#{sub}` + `PROFILE` | `TENANT#{slug}#USER#{sub}` + `PROFILE` |
| Single band | Multiple tenants via `TENANT#{slug}` prefix |
| Cognito groups (admin, manager, editor, band) | Cognito groups + tenant membership |
| No tenant slug in URL | `tenant_slug` from subdomain (e.g. `{tenant}.echo9.net`) |

---

## Feature Tiers

| Tier | Custom Domains | Advanced Analytics |
|------|----------------|-------------------|
| Free | ❌ | ❌ |
| Pro | ✅ | ✅ |
| Business | ✅ | ✅ (+ more) |

---

## Roborev

- Run `roborev status` to check daemon and review queue.
- Run `roborev fix` to auto-fix unaddressed findings.
- Run `roborev refine` to apply fixes and re-check.
- **Required:** Iterate (`roborev fix` → `roborev refine` → commit if needed) until Roborev reports 0 issues. Do not stop with unresolved findings.
- If blocked: mark task as `BLOCKED` in this file.

---

## Blocked / Notes

- **CloudNS vs Route 53:** CloudNS is manageable — official Terraform provider (ClouDNS/cloudns) exists. Tasks 1.11–1.12 automate DNS. **Alternate:** migrate echo9.net to Route 53 for native ACM auto-validation and CloudFront integration; larger migration, no third-party API.
- **CI permissions:** Deploy policy includes S3 bucket read (GetAccelerateConfiguration, GetBucketRequestPayment, GetEncryptionConfiguration, etc.), CloudFront ListTagsForResource, Cognito GetUserPoolMfaConfig/SetUserPoolMfaConfig, Secrets Manager GetResourcePolicy for OpenTofu plan/apply, and IAM self-update (ListPolicyVersions, CreatePolicyVersion, etc.) for deploy policy changes.
- **DynamoDB:** Table-level `hash_key`/`range_key` deprecated (provider does not support table-level `key_schema`). GSI blocks migrated to `key_schema`.
