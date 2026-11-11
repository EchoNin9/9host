# 9host — Unattended Orchestration Runbook (Fable 5.2 Commander + Opus 5.5 + Sonnet)

> **Purpose:** This runbook allows a fresh **Claude CLI** (or `agy-cli`) session with **Fable 5.2** as the Commander/Orchestrator to execute the remaining tickets (`T-02`, `T-03`, `T-04`, `T-06`–`T-12`) of [`docs/SPEC.md`](SPEC.md) **unattended** by delegating implementation and exploration to **Opus 5.5 (`opus`)** and **Sonnet (`sonnet`)** subagents.

---

## 0. Current Handoff State (As of Commit `d58420c`+)

- **Completed & Committed:**
  - `cca3913`: Architectural overhaul spec (`docs/SPEC.md`), `GLOSSARY.md`, ADRs (`0001`, `0002`), and runbook.
  - `f031783` (**`T-01` DONE**): Python 3.11 `.venv` at `/Users/adam/Github/EchoNin9/9host/.venv`, `api/pytest.ini`, `api/tests/conftest.py` (moto single-table `9host-main` with all 4 GSIs `byUser`, `byDomain`, `byEntity`, `bySiteSlug`), `api/html_sanitizer.py` (`sanitize_html()` + 27 passing XSS/rich-text tests), and `frontend/vitest.config.ts`.
  - `d58420c` (**`T-05` DONE**): Fixed Stripe billing bugs (`#6a` VIP-only check so `FREE` can checkout, `#6b` base64 webhook decode + `trialing` status + `VIP` downgrade protection) and added `BILLING_ENABLED` / `VITE_ENABLE_BILLING` feature flag (`false` by default) + 10 backend tests + 10 frontend Vitest tests.
  - **Partial `T-02` Seed Committed:** `api/secrets_cache.py` (`get_secret_string`, `get_secret_json`, `clear_cache` with 5-minute TTL and patchable `_clock` seam) is already written and committed.
- **Test Baseline (All Green):**
  - Backend: `cd /Users/adam/Github/EchoNin9/9host/api && ../.venv/bin/pytest -q` -> **38 passed**
  - Frontend tests: `npm --prefix /Users/adam/Github/EchoNin9/9host/frontend test -- --run` -> **11 passed**
  - Frontend build: `npm --prefix /Users/adam/Github/EchoNin9/9host/frontend run build` -> **0 errors**
- **Remaining Tickets:** `T-02`, `T-03`, `T-04`, `T-06`, `T-07`, `T-08`, `T-09`, `T-10`, `T-11`, `T-12`.

---

## 0.1 Model Routing Matrix (Fable 5.2 Commander -> Opus 5.5 & Sonnet Subagents)

| Role / Wave | Model Tier | Claude CLI `Task` `model` | Why |
|-------------|------------|---------------------------|-----|
| **Commander / Orchestrator** | **Fable 5.2** | Session default (Lead) | Owns the session, writes tight subagent briefs, reviews diffs/test summaries, and commits each ticket. Never reads large files or edits implementation code directly. |
| **Deep Module Implementation (`T-02`, `T-03`, `T-04`, `T-06`, `T-07`, `T-08`, `T-09`, `T-10`)** | **Claude Opus 5.5** | `model: "opus"` | High-precision multi-file Python/TypeScript/OpenTofu refactoring across deep module seams (`RequestContext`, `TenantStore`, `SiteCompiler`, `EdgeHostRouter`, `ApiClient`). |
| **Repo Recon, Packaging Cleanup & Two-Axis Review (`T-11`, `T-12`, and fast file scouting)** | **Claude Sonnet** | `model: "sonnet"` | Fast, low-cost execution for codebase reconnaissance, wheel packaging cleanup (`T-11`), and parallel Standards + Spec `code-review` (`T-12`). |
| **Off-Limits** | **Gemini 4 Argon** | **DO NOT USE** | Argon weekly quota is at 5%. |

---

## 1. Quick-Start Kickoff Prompt (Copy-Paste into New `agy-cli` Session)

Start your new `agy-cli` session with **Opus 5.5 High** (or **Opus 5.5 Medium**) selected as the model, then paste this exact prompt:

```text
/goal Execute the full 9host Architectural Overhaul (Tickets T-01 through T-12) defined in:
- /Users/adam/Github/EchoNin9/9host/GLOSSARY.md
- /Users/adam/Github/EchoNin9/9host/docs/SPEC.md
- /Users/adam/Github/EchoNin9/9host/docs/UNATTENDED_ORCHESTRATION.md
- /Users/adam/Github/EchoNin9/9host/docs/adr/0001-edge-routing-split-and-cloudflare-for-saas.md
- /Users/adam/Github/EchoNin9/9host/docs/adr/0002-deep-module-seams-and-hybrid-auth.md

CRITICAL OPERATING RULES (UNATTENDED ZERO-STOP EXECUTION):
1. NEVER STOP EARLY: Do not pause to ask the user questions, do not stop between waves, and do not stop until all 12 tickets (T-01 to T-12) are implemented, verified, committed, and marked DONE.All architectural decisions are already locked in docs/SPEC.md.
2. QUOTA & CONTEXT PROTECTION (Argon is at 11% — DO NOT USE ARGON):
   - You (Opus 5.5 High) are the Orchestrator/Commander. Keep your own context window lean by delegating implementation and test execution to subagents via `invoke_subagent` (`TypeName="self"` for write/test tasks, `TypeName="research"` for read-only audits).
   - For subagent `Model` parameter:
     * Use `Model="pro"` or `Model="inherit"` for complex deep-module implementation tickets (`T-02`, `T-03`, `T-04`, `T-06`, `T-07`, `T-08`, `T-09`, `T-10`).
     * Use `Model="flash"` for test harness setup, billing flag, packaging cleanup, and the final two-axis review (`T-01`, `T-05`, `T-11`, `T-12`).
3. VERIFIED CREDENTIALS & ENVIRONMENT:
   - Always use `AWS_PROFILE=echo9` and `AWS_REGION=us-east-1` for AWS CLI / OpenTofu commands.
   - ClouDNS API credentials for `echo9.net` (domain ID `1282144`) are verified and stored in AWS Secrets Manager secret `9host-cloudns` (`auth_id=54036`).
4. SKILLS TO FOLLOW: Read `/Users/adam/.gemini/antigravity-cli/skills/tdd/SKILL.md`, `/Users/adam/.gemini/antigravity-cli/skills/codebase-design/SKILL.md`, `/Users/adam/.gemini/config/plugins/delegation-protocol/skills/delegation/SKILL.md`, and `/Users/adam/.gemini/antigravity-cli/skills/code-review/SKILL.md`.
5. WAVE EXECUTION LOOP (T-01 -> T-12):
   - Wave 1: T-01 (Pytest + Vitest harness + HTML sanitizer), T-02 (Deep RequestContext + JWKS/Secret cache + Impersonation fix + Safe 500 errors).
   - Wave 2 (Parallel Subagents): T-03 (Deep TenantStore + SITE_META# fix + adjust_storage_bytes fix), T-04 (Pure SiteCompiler with root `/` links + SiteStoragePort), T-05 (Fix Stripe billing bugs + VITE_ENABLE_BILLING=false feature flag).
   - Wave 3 (Parallel Subagents): T-06 (CloudFront KVS 9host-site-hosts-kvs + cf-site-content.js + cf-preview-content.js HMAC verify), T-07 (CloudflareSaaSAdapter + fallback Worker + delete infra/lambda_acm.tf & lambda_acm_handler), T-08 (Split Admin SPA app/stage.echo9.net vs Public Sites *.echo9.net + S3 7-day noncurrent version lifecycle + ClouDNS records).
   - Wave 4 (Parallel Subagents): T-09 (Migrate API handlers to RequestContext/TenantStore, delete default_site_handler.py, collapse admin_tenant_resources.py), T-10 (Frontend Deep ApiClient, TenantScopeProvider, delete RootRoute, Superadmin-gated Edge KVS/Domains Health panel), T-11 (Move vendored pip packages out of api/ into scripts/build-lambda-package.sh).
   - Wave 5: T-12 (Run full pytest + vitest + frontend build + `tofu -chdir=infra validate`, run parallel Standards & Spec code-review subagents, fix any issues, and commit).
6. COMMIT CONVENTION: After each ticket passes its tests, commit with `agent{N} task {T-XX}: <description>` and update status to DONE in `AGENTS.md` and `docs/UNATTENDED_ORCHESTRATION.md`.
```

---

## 2. Dependency-Graphed Ticket Plan (`T-01` – `T-12`)

```
Wave 1 (Foundation & Test Harness)
  ├── T-01: Pytest + Vitest Harness & HTML Sanitizer (agent1/agent2)
  └── T-02: Deep RequestContext & Auth/Secret Caching (agent1)
        │
Wave 2 (Core Deep Modules — Parallelizable across Subagents)
  ├── T-03: Deep TenantStore & Fix SITE# Scan + Media Delete Crash (agent1)
  ├── T-04: Pure SiteCompiler (Root / Links + XSS Clean) & SiteStoragePort (agent1)
  └── T-05: Fix Stripe Billing Bugs + VITE_ENABLE_BILLING Feature Flag (agent3/agent2)
        │
Wave 3 (Edge Routing Split & Cloudflare for SaaS Custom Domains)
  ├── T-06: CloudFront KVS + cf-site-content.js + Preview HMAC Verify (agent1)
  ├── T-07: CloudflareSaaSAdapter + Delete AWS ACM Custom Domain Infra (agent1)
  └── T-08: Split Admin SPA (app/stage) vs Public Sites (*.echo9.net) + S3 Lifecycle (agent1)
        │
Wave 4 (Handler Consolidation, Frontend Deepening & Packaging)
  ├── T-09: Migrate API Handlers to RequestContext/TenantStore & Drop Duplicate Admin CRUD (agent1)
  ├── T-10: Frontend Deep ApiClient, Delete RootRoute, & Unify Admin/Tenant Views (agent2)
  └── T-11: Clean Vendored Wheels from api/ into Build Artifact Step (agent1)
        │
Wave 5 (End-to-End Verification & Two-Axis Code Review)
  └── T-12: Full Regression Suite, OpenTofu Validate, & Spec/Standards Review Gate (all)
```

---

## 3. Detailed Ticket Specifications & Acceptance Criteria

### `T-01`: Pytest + Vitest Harness & HTML Sanitizer (`[DONE]`)
- **Agent:** `agent1` / `agent2`
- **Blocked by:** None
- **Scope:**
  - Create `api/pytest.ini` and `api/tests/conftest.py`.
  - Create `api/html_sanitizer.py` implementing a pure stdlib `HTMLParser`-based allowlist sanitizer (`sanitize_html(raw_html: str) -> str`) that strips `<script>`, `<iframe>`, `<object>`, `<embed>`, `<style>`, `on*` event attributes, and `javascript:` / `data:text/html` URLs.
  - Configure `vitest` in `frontend/package.json` (`"test": "vitest"`).
- **Acceptance Criteria:**
  - `pytest api/tests/test_html_sanitizer.py` passes (covering XSS payloads and valid rich-text formatting).
  - `npm --prefix frontend test -- --run` executes cleanly.

### `T-02`: Deep `RequestContext` & Auth/Secret Caching (`[DONE]`)
- **Agent:** `agent1`
- **Blocked by:** `T-01`
- **Scope:**
  - Implement `api/request_context.py` per `docs/SPEC.md §3 Module 2`.
  - Add local Cognito JWT verification using cached JWKS (with fallback to `cognito-idp.get_user` only if JWKS env is unconfigured in local dev) and module-cached Secrets Manager lookups (5-minute TTL).
  - Resolve Superadmin `X-Impersonate-Tenant` and `/api/admin/tenants/{slug}/*` path parameters once so `ctx.effective_role == "admin"` (`Bug #5` fix).
  - Implement safe error boundary and `Decimal` serializer (`Bug #8` fix: never return `detail.traceback` in HTTP 500 responses).
- **Acceptance Criteria:**
  - `pytest api/tests/test_request_context.py` passes 100% (testing Cognito token, `TUSER` token, Superadmin impersonation role override, unauthorized rejection, and 500 stack-trace scrubbing).

### `T-03`: Deep `TenantStore` & Fix `SITE#` Scan + Media Delete Crash (`[DONE]`)
- **Agent:** `agent1`
- **Blocked by:** `T-01`
- **Scope:**
  - Implement `api/tenant_store.py` with `DynamoDBTenantStore` and `InMemoryTenantStore` per `docs/SPEC.md §3 Module 3`.
  - Fix `Bug #3`: Ensure `list_sites(tenant_slug)` only reads site metadata items (`SK = SITE_META#{id}` with backward-compatible fallback/migration from `SK = SITE#{id}` where `sk` has no second `#`) and never scans `SITE#{id}#PAGE/POST/EVENT/MEDIA`.
  - Fix `Bug #4`: Implement `adjust_storage_bytes(tenant_slug, delta_bytes)` using conditional atomic updates (`ConditionExpression="storage_used_bytes >= :abs_delta"`, setting `0` on `ConditionalCheckFailedException`) instead of invalid `greatest()`.
  - Replace full-table scans in `api/admin_handler.py` and `api/admin_users_handler.py` with GSI/partition queries where applicable.
- **Acceptance Criteria:**
  - `pytest api/tests/test_tenant_store.py` passes against both `InMemoryTenantStore` and mocked `DynamoDBTenantStore` (verifying `adjust_storage_bytes` never underflows below 0 and `list_sites` ignores content rows).

### `T-04`: Pure `SiteCompiler` (Root `/` Links + XSS Clean) & `SiteStoragePort` (`[DONE]`)
- **Agent:** `agent1`
- **Blocked by:** `T-01`, `T-03`
- **Scope:**
  - Create `api/site_compiler.py` (`compile_site(snapshot, mode) -> CompiledSiteBundle`) and `api/site_storage.py` (`S3SiteStorageAdapter` + `InMemorySiteStorage`).
  - Update `api/templates/base_layout.py` and all 5 template renderers (`musician_band`, `personal_tech`, `personal_resume`, `professional_services`, `business_generic`) so:
    1. All rich-text fields pass through `sanitize_html()`.
    2. Live mode (`mode="live"`) uses root-relative paths (`/`, `/blog/`, `/posts/{slug}/`, `/events/`, `/gallery/`) instead of `/site/{tenant}/{site_id}/`.
    3. Draft mode (`mode="draft"`) uses `/preview` prefix.
  - Refactor `api/publish_handler.py` (`_publish_site`, `_draft_publish_site`, `_rollback_site`) to delegate to `compile_site` + `SiteStoragePort`.
- **Acceptance Criteria:**
  - `pytest api/tests/test_site_compiler.py` passes (verifying all 5 templates render valid HTML, root-relative links in `live` mode, `/preview` links in `draft` mode, and zero `<script>` tags survive in user content).

### `T-05`: Fix Stripe Billing Bugs + `VITE_ENABLE_BILLING` Feature Flag (`[DONE]`)
- **Agent:** `agent3` / `agent2`
- **Blocked by:** `T-01`
- **Scope:**
  - Fix `Bug #6a` in `api/billing_handler.py`: Change `if tenant and not is_payable_tier(tenant.get("tier", "FREE")):` to `if tenant and tenant.get("tier", "FREE").upper() == "VIP":` in both `_create_checkout` and `_create_portal`.
  - Fix `Bug #6b` in `api/stripe_webhook_handler.py`:
    1. Decode `event["body"]` with `base64.b64decode` when `event.get("isBase64Encoded")` is `True`.
    2. Before downgrading a tenant to `"FREE"` on subscription cancellation/unpaid events, check if the tenant's current tier is `"VIP"` (never overwrite `VIP`), and treat `"trialing"` as active.
  - Add `BILLING_ENABLED` check in `api/billing_handler.py` and `VITE_ENABLE_BILLING` (default `false`) in `frontend/src/lib/feature-flags.ts`, hiding Billing UI in `tenant-settings.tsx` and upgrade prompts in `FeatureGate.tsx` when `false`.
- **Acceptance Criteria:**
  - `pytest api/tests/test_billing_and_webhooks.py` and `npm --prefix frontend test -- --run` pass.

### `T-06`: CloudFront KVS + `cf-site-content.js` + Preview HMAC Verify (`[DONE]`)
- **Agent:** `agent1`
- **Blocked by:** `T-04`
- **Scope:**
  - Add `aws_cloudfront_key_value_store.site_hosts` (`9host-site-hosts-kvs`) in `infra/cloudfront.tf` and associate it with `aws_cloudfront_function.site_content`.
  - Update `infra/cf-site-content.js` to resolve `x-forwarded-host || host` via `cf.kvs()` (`HostMappingKVS`) and rewrite `request.uri` to `/{tenant}/{site_id}/published/current/...` at `/`, while preserving backward compatibility for `/site/{tenant}/{site_id}/...`.
  - Update `infra/cf-preview-content.js` (`Bug #8` fix) to verify the JWT HMAC-SHA256 signature using `crypto.subtle` and a secret read from KVS (`__preview_jwt_secret__`) before serving `/draft/` content.
  - Wire `SiteStoragePort` to write/delete KVS host mappings via `boto3.client("cloudfront-keyvaluestore")` whenever a site is published or deleted.
- **Acceptance Criteria:**
  - `pytest api/tests/test_edge_kvs_sync.py` passes and `tofu -chdir=infra validate` succeeds.

### `T-07`: `CloudflareSaaSAdapter` + Delete AWS ACM Custom Domain Infra (`[DONE]`)
- **Agent:** `agent1`
- **Blocked by:** `T-06`
- **Scope:**
  - Create `api/cloudflare_saas.py` implementing custom hostname creation, status check, and deletion against Cloudflare Custom Hostnames API (`POST/GET/DELETE /zones/{zone_id}/custom_hostnames`), returning `cname_target = "proxy.echo9.net"` and ownership verification TXT records.
  - Create `infra/cloudflare-worker/custom-domain-proxy.js` and `infra/cloudflare-worker/wrangler.toml` for the 12-line fallback origin Worker on `echo9.net`.
  - Refactor `api/custom_domain_handler.py` and `api/domains_handler.py` to use `CloudflareSaaSAdapter` + `HostMappingKVS` (syncing `domain -> {tenant, site_id}` into KVS when domain becomes `ACTIVE`).
  - Delete `infra/lambda_acm.tf` and `infra/lambda_acm_handler/`.
- **Acceptance Criteria:**
  - `pytest api/tests/test_cloudflare_saas.py` passes and `tofu -chdir=infra validate` succeeds with `lambda_acm.tf` removed.

### `T-08`: Split Admin SPA (`app`/`stage`) vs Public Sites (`*.echo9.net`) + S3 Lifecycle (`[DONE]`)
- **Agent:** `agent1`
- **Blocked by:** `T-06`, `T-07`
- **Scope:**
  - In `infra/cloudfront.tf`:
    - Update `aws_cloudfront_distribution.frontend` aliases to serve `app.echo9.net` (prod) and `stage.echo9.net` (staging).
    - Update `aws_cloudfront_distribution.sites` so its `default_cache_behavior` (`/*`) targets `S3-9host-sites` with `cf-site-content.js` (instead of `S3-9host-frontend` with `cf-spa-routing.js`), and include `echo9.net` and `www.echo9.net` in aliases for the landing page.
  - In `infra/cloudns/`: Add `app.echo9.net` CNAME -> `aws_cloudfront_distribution.frontend.domain_name` and `sites-origin.echo9.net` CNAME -> `aws_cloudfront_distribution.sites.domain_name`.
  - In `infra/s3.tf` (`Bug #9` fix): Add `aws_s3_bucket_lifecycle_configuration` to `9host-sites` and `9host-media` expiring `noncurrent_version_expiration` after `7` days.
- **Acceptance Criteria:**
  - `tofu -chdir=infra validate` passes with 0 errors.

### `T-09`: Migrate API Handlers to `RequestContext`/`TenantStore` & Drop Duplicate Admin CRUD (`[DONE]`)
- **Agent:** `agent1`
- **Blocked by:** `T-02`, `T-03`, `T-04`, `T-07`
- **Scope:**
  - Wire `api/handler.py`, `api/content_handler.py`, `api/sites_handler.py`, `api/domains_handler.py`, `api/users_handler.py`, `api/tenant_users_handler.py`, `api/roles_handler.py`, and `api/upload_handler.py` to use `RequestContext` and `TenantStore`.
  - Delete `api/default_site_handler.py` and remove `/api/tenant/default-site` route from `api/handler.py`.
  - Collapse `api/admin_tenant_resources.py` so `/api/admin/tenants/{slug}/*` delegates to the unified tenant handlers with an admin-impersonated `RequestContext`.
- **Acceptance Criteria:**
  - `pytest api/tests/` passes all handler integration tests (including Superadmin editing pages/posts/events/media while impersonating a tenant).

### `T-10`: Frontend Deep `ApiClient`, Delete `RootRoute`, & Unify Admin/Tenant Views (`[DONE]`)
- **Agent:** `agent2`
- **Blocked by:** `T-05`, `T-09`
- **Scope:**
  - Create `frontend/src/lib/api-client.ts` and `frontend/src/context/tenant-scope.tsx`.
  - Refactor `frontend/src/lib/api.ts` to delegate all calls through `apiClient` (eliminating global `_impersonateTenant` race conditions and separating `9host_cognito_token` from `9host_site_token`).
  - Remove `RootRoute` and `fetchDefaultSite` from `frontend/src/App.tsx`.
  - Update `frontend/src/components/custom-domain-wizard.tsx` to display the simplified Cloudflare for SaaS instructions (`CNAME -> proxy.echo9.net` + TXT validation record).
  - Refactor `frontend/src/components/administer-tenant.tsx` to reuse the tenant resource components via `<TenantScopeProvider>`.
  - Add the **Superadmin-Only Live Edge Routing & Domains Health Panel** (`9host-site-hosts-kvs`) inside the Superadmin Console (`/admin`, gated by `require_superadmin()`), and ensure the public `(www.)echo9.net` landing template never exposes tenant domain lists or KVS entries.
- **Acceptance Criteria:**
  - `npm --prefix frontend test -- --run` and `npm --prefix frontend run build` pass with 0 TypeScript or bundle errors.

### `T-11`: Clean Vendored Wheels from `api/` into Build Artifact Step (`[DONE]`)
- **Agent:** `agent1`
- **Blocked by:** `T-09`
- **Scope:**
  - Create `scripts/build-lambda-package.sh` that installs `api/requirements.txt` into `infra/.build/api_lambda/` and copies `api/*.py` and `api/templates/`.
  - Update `infra/lambda.tf` `data.archive_file.api_lambda` to package `infra/.build/api_lambda` (auto-building via local-exec or CI pre-step) and update `.github/workflows/dev.yml` and `main.yml`.
  - Remove vendored third-party directories (`api/stripe/`, `api/jwt/`, `api/bcrypt/`, `api/requests/`, `api/urllib3/`, `api/idna/`, `api/certifi/`, `api/charset_normalizer/`, `api/bin/`, `api/*.dist-info/`) from `api/` and add `infra/.build/` to `.gitignore`.
- **Acceptance Criteria:**
  - `scripts/build-lambda-package.sh` builds a clean Lambda zip, `pytest api/tests/` passes, and `git status` shows vendored wheel directories removed from `api/`.

### `T-12`: Full Regression Suite, OpenTofu Validate, & Spec/Standards Review Gate (`[DONE]`)
- **Agent:** All (`code-review` subagents)
- **Blocked by:** `T-01` through `T-11`
- **Scope:**
  - Run all verification commands:
    - `pytest api/tests/ -v`
    - `npm --prefix frontend test -- --run`
    - `npm --prefix frontend run build`
    - `tofu -chdir=infra validate`
  - Spawn two parallel `research` subagents (`Model="flash"`) per the `code-review` skill:
    1. **Standards Reviewer:** Checks `CLAUDE.md`, `AGENTS.md`, and `GLOSSARY.md` compliance.
    2. **Spec Reviewer:** Checks all 9 bug fixes and 6 user stories in `docs/SPEC.md`.
  - Fix any findings and mark all tasks `DONE`.

---

## 4. ClouDNS (`echo9.net` Zone `1282144`) & `tools.e9.cx` Redirect Transition

### Verified Live ClouDNS State (`AWS_PROFILE=echo9`, Secret `9host-cloudns`, `auth_id=54036`)
We verified live API access against `https://api.cloudns.net/dns/records.json` for `echo9.net` (`46` active records):
- **Record `180304152`:** `host=""` (bare `echo9.net`), `type="WR"` (Web Redirect) -> `https://tools.e9.cx`
- **Record `180304155`:** `host="www"` (`www.echo9.net`), `type="WR"` (Web Redirect) -> `https://tools.e9.cx`
- **Record `740575166`:** `host="prod"`, `type="CNAME"` -> `d1y8o0nam8q0rq.cloudfront.net` (`frontend` prod dist)
- **Record `740575171`:** `host="stage"`, `type="CNAME"` -> `d327su5s05gt98.cloudfront.net` (`frontend` stage dist)
- **Records `747760163`+ (`jinks1`, `jinks2`, `jinks3`, `jinks4`, `oliver`, `jinks-ca`, `oliverjinks-com`):** `type="CNAME"` -> `d2nqdv42n1qlhv.cloudfront.net` (`sites` dist)

### What Happens to the `echo9.net -> tools.e9.cx` Redirect (`T-08`)
1. **Add `tools.echo9.net` Web Redirect (`WR`):** Create `host="tools"`, `type="WR"` -> `https://tools.e9.cx` in ClouDNS so `tools.echo9.net` always redirects to `tools.e9.cx`.
2. **Prominent `tools.e9.cx` Launch Button on `www.echo9.net`:** The new `(www.)echo9.net` landing page includes a permanent **`⚡ Echo9 Tools (tools.e9.cx ↗)`** pill button in the top navigation bar and hero actions (see [`docs/ui-mockups.html`](ui-mockups.html)).
3. **Cut Over `@` (`180304152`) and `www` (`180304155`) in ClouDNS:**
   - Delete or update `WR` record `180304155` (`www`) to `CNAME www -> d2nqdv42n1qlhv.cloudfront.net` (`sites` CloudFront distribution).
   - Update `WR` record `180304152` (`@`) to either redirect `echo9.net -> https://www.echo9.net` (301) or `ALIAS -> d2nqdv42n1qlhv.cloudfront.net`.
   - Add `CNAME app -> d1y8o0nam8q0rq.cloudfront.net` (`frontend` production Admin SPA distribution).

---

## 5. One-Time Setup Checklist for Cloudflare for SaaS Custom Domains (`Option B2`)

Because Cloudflare account configuration happens in your Cloudflare dashboard, complete these 5 steps once when you are ready to route live domains:

1. **Add `echo9.net` Zone to Cloudflare (Free Plan):**
   - In Cloudflare Dashboard -> **Add a domain** -> `echo9.net` (Free plan).
   - Remove the old `echo9.net -> tools.e9.cx` redirect rule.
2. **Create DNS Records in Cloudflare `echo9.net`:**
   - `CNAME app` -> `<frontend-cloudfront-domain>.cloudfront.net` (DNS only / grey cloud, since CloudFront terminates `*.echo9.net` ACM cert).
   - `CNAME stage` -> `<staging-frontend-cloudfront-domain>.cloudfront.net` (DNS only / grey cloud).
   - `CNAME *` -> `<sites-cloudfront-domain>.cloudfront.net` (DNS only / grey cloud).
   - `CNAME sites-origin` -> `<sites-cloudfront-domain>.cloudfront.net` (DNS only / grey cloud).
   - `AAAA proxy` -> `100::` (Proxied / **orange cloud** — acts as the Cloudflare for SaaS Fallback Origin).
3. **Enable Cloudflare for SaaS (Custom Hostnames):**
   - In Cloudflare Dashboard -> `echo9.net` -> **SSL/TLS** -> **Custom Hostnames**.
   - Enable Cloudflare for SaaS (first 100 hostnames are **$0/month**).
   - Set **Fallback Origin** to `proxy.echo9.net`.
4. **Deploy the Fallback Origin Worker:**
   - Run `npx wrangler deploy` inside `infra/cloudflare-worker/` (binds route `proxy.echo9.net/*` and `*/*` custom hostnames to forward requests to `https://sites-origin.echo9.net` with `X-Forwarded-Host`).
5. **Save Cloudflare API Token in AWS Secrets Manager (`9host-cloudflare`):**
   - Create a Cloudflare API Token with `Zone:SSL and Certificates:Edit` for `echo9.net`.
   - Store `{"zone_id": "<your-zone-id>", "api_token": "<your-api-token>"}` in AWS Secrets Manager secret `9host-cloudflare`.

---

## 6. Deploy Cutover Order (`T-06`–`T-08`) — READ BEFORE PUSHING `develop`

`.github/workflows/dev.yml` / `main.yml` run a full `tofu apply` on push. Nothing in `T-06`–`T-08` has been applied. Follow this order:

1. **Certs first (local, before pushing):** `tofu -chdir=infra apply -target=aws_acm_certificate.main -target=aws_acm_certificate.wildcard -var='domains=["echo9.net"]'`, then add the new `app.echo9.net` validation CNAME from `tofu output acm_validation_records` to ClouDNS. If you push first, CI waits ~75 min on `aws_acm_certificate_validation.main` and fails (safely).
2. **Full apply** once both certs are `ISSUED`. `production` gains `app.echo9.net`; the `sites` default behaviour switches to static HTML via `cf-site-content.js` (unmapped hosts return 404). The first apply may hit AccessDenied creating the KVS because the deploy-role policy update lands in the same apply — rerun. The apply also destroys the `9host-acm-handler` Lambda, role and EventBridge rule.
3. **ClouDNS (`infra/cloudns`)**: local state holds `cloudns_dns_zone.echo9_net` but config uses `cloudns_dns_zone.zone["echo9.net"]` — a plain apply would plan to destroy the zone. Run `tofu state mv cloudns_dns_zone.echo9_net 'cloudns_dns_zone.zone["echo9.net"]'` first, then apply with `-var manage_records=false` (creates `app`, `sites-origin`, `tools` records).
4. **Republish every site** (or backfill KVS) so `{slug}.echo9.net` mappings exist — mappings are only written on publish, and unmapped hosts now 404.
5. Move admins to `app.echo9.net` (Cognito callback/logout URLs already include it); remove the `prod` alias/record after traffic drains.
6. **Landing page:** unmanaged distribution `E164B9WJ8ALT9F` still holds `echo9.net` / `www.echo9.net`. Remove them there by hand, then set `serve_landing_domain = true` and `landing_site = {tenant, site_id}` and apply.
7. **ClouDNS `@` / `www` (manual, only after step 6):** `www` (`180304155`) WR -> `CNAME d2nqdv42n1qlhv.cloudfront.net`; `@` (`180304152`) -> 301 to `https://www.echo9.net` or ALIAS to the sites distribution.
8. **Existing ACM-era custom domains** re-register with Cloudflare on their next status check and stay `PENDING_VALIDATION` until the tenant points `CNAME -> proxy.echo9.net`; delete orphaned ACM certs by hand.

Known spec deviations: there is no `aws_cloudfront_distribution.frontend` (the SPA is `staging` + `production`), no `/api/*` CloudFront behaviour (SPA calls API Gateway via `VITE_API_URL`), and `cf-preview-content.js` uses `crypto.createHmac` (CloudFront Functions have no `crypto.subtle`).
