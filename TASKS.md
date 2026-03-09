# 9host — Multi-Tenant Website Hosting Platform

> **Branch strategy:** `main` = prod (prod.echo9.net) | `develop` = dev (stage.echo9.net)  
> **Agent roles:** agent1 (backend/infra) | agent2 (frontend/ui) | agent3 (payments)  
> **AWS naming:** All AWS resources MUST use prefix `9host` (e.g. 9host-main, 9host-api, 9host-user-pool, 9host-media)  
> **Agent workflow:** Update task status (TODO → DONE) in this file when completing work.

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

### Agent 2 — Frontend / UI

| ID | Task | Status | Notes |
|----|------|--------|-------|
| 2.0 | Scaffold Shadcn/UI (components.json, base components) | TODO | `npx shadcn@latest init` |
| 2.1 | Design Tenant Admin Sidebar | TODO | Multi-tenant navigation; use Shadcn/UI |
| 2.2 | Create FeatureFlag utility (Free, Pro, Business tiers) | TODO | Pro unlocks: Custom Domains, Advanced Analytics |
| 2.3 | Create HOC `withFeatureGate` to wrap restricted UI elements | TODO | Align with saas-architecture.mdc `<FeatureGate>` |
| 2.4 | Implement tenant context provider (tenant_slug from URL) | TODO | For use in components |
| 2.5 | Migrate single-user UI to multi-tenant (tenant switcher, routing) | TODO | |

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

**Status:** SSL certs validated. GitHub repo vars (AWS_ROLE_ARN_STAGING, AWS_ROLE_ARN_PRODUCTION) added.

**Next:** Task 1.5 (CI/CD) or CloudFront setup.

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

_Add blockers here._
