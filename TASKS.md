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
| 2.14 | Tenantadmin UI: users list, role management | TODO | Tenantadmin sees all tenantadmins & tenantusers. Depends on 1.24, 1.27. |
| 2.15 | Module access UI: tenantadmin configures per-user permissions | TODO | Tenantuser sees only what tenantadmin allows. Depends on 1.25. |
| 2.16 | Role-based UI: hide create/edit/delete for tenantuser in Sites, Domains, Settings | DONE | useTenantRole hook, canEdit for admin/manager. editor/member see view-only. |
| 2.17 | Tenant Settings: show owner, transfer owner (if owner) | TODO | Depends on 1.26. owner_sub on tenant. |

### Agent 3 — Payments

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 3.1 | Integrate Stripe for tier subscriptions (Free, Pro, Business) | TODO | |
| 3.2 | Map Stripe subscription status → FeatureFlag tier | TODO | |
| 3.3 | Implement upgrade/downgrade flows and webhooks | TODO | |

---

## Save Points

> **Use when pausing work.** Document where you stopped and what to do next.

### ~~Save Point: SSL certificates created (Phase 1)~~ ✅ Complete

**Status:** SSL certs validated. GitHub repo vars (AWS_ROLE_ARN_STAGING, AWS_ROLE_ARN_PRODUCTION) added. Tasks 1.0–1.24 complete (schema, DynamoDB, middleware, CI/CD, CloudNS, admin API, impersonation, role checks, Stripe webhook stub, migration script). Tasks 2.0–2.13 complete (sidebar, FeatureFlag, tenant context, auth, Sites/Domains/Analytics UI, superadmin UI).

**Next:** Tasks 1.25–1.27 (module permissions, owner_sub, tenant users API), 2.14–2.17 (tenantadmin users, role-based UI, settings owner), or Agent 3 (Stripe subscriptions).

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
