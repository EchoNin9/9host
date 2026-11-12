# 9host — Development Status

## Agent Roles

| Agent | Focus | Expertise |
|-------|-------|-----------|
| **agent1** | Backend / Infra | OpenTofu, AWS CloudFront KVS, Cloudflare for SaaS, DynamoDB Single Table (`TenantStore`), Lambda (`RequestContext`, `SiteCompiler`), Cognito + `TUSER` Hybrid Auth (all AWS resources prefixed `9host`) |
| **agent2** | Frontend / UI | React, Vite, Tailwind, Shadcn/UI, `ApiClient`, `TenantScopeProvider`, `FeatureGate` + `VITE_ENABLE_BILLING` flag |
| **agent3** | Payments | Stripe API, subscriptions, webhooks, `VIP` / `FREE` / `PRO` / `BUSINESS` tier mapping |

## Tech Stack

- **Backend:** AWS Lambda, API Gateway, DynamoDB (`9host-main` single-table behind `TenantStore`). All AWS resources use prefix `9host`.
- **Edge & Custom Domains:**
  - `app.echo9.net` (prod) / `stage.echo9.net` (stage): React Admin & Superadmin SPA.
  - `*.echo9.net` + `(www.)echo9.net`: Public static sites served directly from `S3-9host-sites` at `/` via `cf-site-content.js` + CloudFront KeyValueStore (`HostMappingKVS`).
  - Custom Domains: **Cloudflare for SaaS** on `echo9.net` (`CNAME -> proxy.echonin9.com`) + fallback Worker forwarding `X-Forwarded-Host` to CloudFront.
- **Auth:** Hybrid Cognito User Pool (`USER#{sub}` for Tenant Admins / Superadmins) + DynamoDB `TUSER` / `ROLE` / `GROUP` entities unified inside `RequestContext`.
- **Frontend:** React + Vite + TypeScript + Tailwind CSS + Shadcn/UI.

> **Next work starts here:** [`docs/RUNBOOK_POST_CUTOVER.md`](docs/RUNBOOK_POST_CUTOVER.md) (post-cutover tasks A–F, guardrails, live resource IDs).

## Architecture & Unattended Execution Documents

Before starting work, read:
1. **[`GLOSSARY.md`](GLOSSARY.md)** — Canonical domain and deep-module terminology.
2. **[`docs/SPEC.md`](docs/SPEC.md)** — Full technical specification for the 5 deep modules and 9 bug fixes.
3. **[`docs/UNATTENDED_ORCHESTRATION.md`](docs/UNATTENDED_ORCHESTRATION.md)** — Dependency-graphed tickets (`T-01` – `T-12`) and unattended Claude Opus 4.6 execution runbook.
4. **[`docs/adr/0001-edge-routing-split-and-cloudflare-for-saas.md`](docs/adr/0001-edge-routing-split-and-cloudflare-for-saas.md)** & **[`docs/adr/0002-deep-module-seams-and-hybrid-auth.md`](docs/adr/0002-deep-module-seams-and-hybrid-auth.md)**.

## Active Overhaul Tickets (`docs/UNATTENDED_ORCHESTRATION.md`)

- [x] `T-01`: Pytest + Vitest Harness & HTML Sanitizer [agent1/agent2] — DONE
- [x] `T-02`: Deep `RequestContext` & Auth/Secret Caching [agent1] — DONE
- [x] `T-03`: Deep `TenantStore` & Fix `SITE#` Scan + Media Delete Crash [agent1] — DONE
- [x] `T-04`: Pure `SiteCompiler` (Root `/` Links + XSS Clean) & `SiteStoragePort` [agent1] — DONE
- [x] `T-05`: Fix Stripe Billing Bugs + `VITE_ENABLE_BILLING` Feature Flag [agent3/agent2] — DONE
- [x] `T-06`: CloudFront KVS + `cf-site-content.js` + Preview HMAC Verify [agent1] — DONE
- [x] `T-07`: `CloudflareSaaSAdapter` + Delete AWS ACM Custom Domain Infra [agent1] — DONE
- [x] `T-08`: Split Admin SPA (`app`/`stage`) vs Public Sites (`*.echo9.net`) + S3 Lifecycle [agent1] — DONE (code only; see runbook §6 before pushing)
- [x] `T-09`: Migrate API Handlers to `RequestContext`/`TenantStore` & Drop Duplicate Admin CRUD [agent1] — DONE
- [x] `T-10`: Frontend Deep `ApiClient`, Delete `RootRoute`, & Unify Admin/Tenant Views [agent2] — DONE
- [x] `T-11`: Clean Vendored Wheels from `api/` into Build Artifact Step [agent1] — DONE
- [x] `T-12`: Full Regression Suite, OpenTofu Validate, & Spec/Standards Review Gate [all] — DONE

**Deployed (2026-11-12).** `develop` and `main` are both live (PR #16, merge `f3f7741`); the §6 cutover is complete. Pushes to `develop`/`main` run `tofu apply` + frontend deploy via CI. Remaining operational steps are listed under "PROGRESS 2026-11-12" in runbook §6.

## Follow-On Tickets (`docs/UNATTENDED_ORCHESTRATION.md` §7)

Full scope, files, and acceptance criteria for each are in runbook §7. `T-13`–`T-18` are code-only and independent of the deploy; `T-19` needs the §6 cutover done first. Commit locally only — do not push without the §6 cutover.

- [ ] `T-13`: Migrate remaining legacy-auth handlers to `RequestContext` & delete `auth_helpers`/`middleware` auth path [agent1]
- [ ] `T-14`: Atomic site-metadata writes, S3 cleanup on site delete, migration marker on tenant create [agent1]
- [ ] `T-15`: Verify & enforce custom `ROLE` permissions server-side [agent1]
- [ ] `T-16`: CI test gate, deploy-role KVS scoping, untrack `infra/api.zip`, `tofu fmt` drift [agent1]
- [ ] `T-17`: `byEntity` index entries for tenants/domains to replace superadmin scans [agent1]
- [ ] `T-18`: Small hardening (sanitizer `rel`, `X-Forwarded-Host` trust, Cloudflare poll throttle, admin console polish) [agent1/agent2]
- [ ] `T-19`: Post-deploy runtime verification (edge functions, Lambda bundle, Cloudflare, browser) [all] — blocked by §6
