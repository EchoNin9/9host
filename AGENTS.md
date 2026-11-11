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
  - Custom Domains: **Cloudflare for SaaS** on `echo9.net` (`CNAME -> proxy.echo9.net`) + fallback Worker forwarding `X-Forwarded-Host` to CloudFront.
- **Auth:** Hybrid Cognito User Pool (`USER#{sub}` for Tenant Admins / Superadmins) + DynamoDB `TUSER` / `ROLE` / `GROUP` entities unified inside `RequestContext`.
- **Frontend:** React + Vite + TypeScript + Tailwind CSS + Shadcn/UI.

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

**Not deployed.** Nothing has been pushed or applied. Follow `docs/UNATTENDED_ORCHESTRATION.md` §6 before pushing `develop` (push triggers `tofu apply`).

Known follow-ups (accepted at the T-12 review gate):
- Handlers still on legacy `auth_helpers`: billing, analytics, templates, validate-slug, `/api/tenant`, other `admin_*`.
- `advanced_analytics` backend gate ignores `module_overrides`.
- CI deploy role KVS statement uses `Resource = "*"`; CI runs no pytest/vitest/edge tests.
- Publish/rollback site-metadata writes are read-then-write (not atomic); site delete leaves S3 objects.
- `infra/api.zip` is still tracked in git; sanitizer keeps `target="_blank"` without `rel="noopener"`.
- Edge functions and the Linux Lambda bundle are only tested locally with stubs, never on the real runtimes.
