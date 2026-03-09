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
| 1.0 | Create SSL certificates (ACM + Route 53 DNS validation) | TODO | `infra/` OpenTofu. **STOP after apply.** DNS validation takes 5–30 min (up to 72h). See Save Point below |
| 1.1 | Analyze orangewhip schema (User, Profile) and design Tenant model for DynamoDB | TODO | Reference: `../orangewhip.surf` (USER#sub, PROFILE). Add TENANT#{slug} prefix to all PKs |
| 1.2 | Extend DynamoDB single-table: TENANT#{slug}, TENANT#{slug}#USER#{sub}#PROFILE, etc. | TODO | Table name: `9host-main`. Every item MUST have PK starting with TENANT# |
| 1.3 | Implement middleware: extract `tenant_slug` from URL (e.g. `{tenant}.echo9.net`) and inject into Lambda context | TODO | Pass tenant_slug to handler; use in all DynamoDB queries |
| 1.4 | Add GSIs for tenant-scoped queries (byTenant, byTenantEntity, etc.) | TODO | Tenant isolation via PK prefix |
| 1.5 | Set up CI/CD: push to `develop` → stage.echo9.net, merge to `main` → prod.echo9.net | TODO | Similar to orangewhip dev.yml / main.yml. All AWS resources prefixed `9host` |
| 1.6 | Integrate Roborev post-commit hooks for PR reviews | TODO | `roborev init` in repo |

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

### Save Point: SSL certificates created (Phase 1)

**When:** After running `tofu apply` in `infra/` and cert + DNS validation records are created.

**Status:** Cert is in "Pending validation". DNS records must propagate before ACM issues the cert.

**Do NOT proceed** until:
1. You have delegated the domain to Route 53 (add NS records from `tofu output route53_name_servers` at your registrar).
2. ACM certificate status shows "Issued" in AWS Console (Certificate Manager, us-east-1).

**Next step:** Once cert is Issued, continue with task 1.5 (CI/CD) or CloudFront setup. Add `aws_acm_certificate_validation` resource when building CloudFront.

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
