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

- [x] `T-13`: Migrate remaining legacy-auth handlers to `RequestContext` & delete `auth_helpers`/`middleware` auth path [agent1] — DONE `9033b46`
- [x] `T-14`: Atomic site-metadata writes, S3 cleanup on site delete, migration marker on tenant create [agent1] — DONE `e61f57b`
- [x] `T-15`: Verify & enforce custom `ROLE` permissions server-side [agent1] — DONE `519e416`
- [x] `T-16`: CI test gate, deploy-role KVS scoping, untrack `infra/api.zip`, `tofu fmt` drift [agent1] — DONE `e549b3d, ce1e516, 1398c06` (ClouDNS provider bug → T-24)
- [x] `T-17`: `byEntity` index entries for tenants/domains to replace superadmin scans [agent1] — DONE `f26969b`
- [x] `T-18`: Small hardening (sanitizer `rel`, `X-Forwarded-Host` trust, Cloudflare poll throttle, admin console polish) [agent1/agent2] — DONE `53a27b4` (edge-function part reverted in 3394394/aa3ad44 → T-21; prod /media/* → T-22)
- [x] `T-19`: Post-deploy runtime verification (edge functions, Lambda bundle, Cloudflare, browser) [all] — DONE `d8c90e2` (browser checks need owner)
- [x] `T-20`: Superadmin users console: list platform admins (Cognito `superadmin` group, e.g. app.echo9.net admins) in their own section above tenant admins instead of under "Orphaned users" [agent1/agent2] — owner request 2026-11-12 — DONE `7d2c0d4`
- [x] `T-21`: Re-land the X-Forwarded-Host proxy-secret edge check (verify with `aws cloudfront test-function`; add a CI test-function step) [agent1] — DONE `5f088e4`
- [x] `T-22`: `/media/*` cache behaviour on the production Admin SPA distribution [agent1] — DONE `55de689`
- [x] `T-23`: Enforce remaining CustomRole permission keys (domains, analytics, settings, users) [agent1] — DONE `f068e73`
- [x] `T-24`: ClouDNS provider read bug: upstream fix or move echo9.net edge records to an API script [agent1] — DONE `b9b544f`
- [ ] `T-25`: (owner) Expired echo9.net cert on non-9host distribution E164B9WJ8ALT9F [owner]
- [ ] `T-26`: (owner decision) Restyle Admin SPA to match ui-mockups.html screens 2–4 (theme, Sites cards, sidebar, domains table, superadmin console) [agent2]
- [ ] `T-27`: (owner decision) Make `editor` an assignable TUSER role? [agent1]
- [ ] `T-28`: CI test-function gate depends on `jinks4.echo9.net` staying mapped [agent1]

`T-21`–`T-24` outcomes, the owner's `T-21` proxy-secret rollout commands and new tickets `T-27`/`T-28`: runbook §7 status.

Post-cutover runbook outcomes (A–F) and the landing production cutover steps: `docs/RUNBOOK_POST_CUTOVER.md` §5–§6.
