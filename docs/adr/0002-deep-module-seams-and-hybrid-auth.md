# ADR-0002: Deep Module Seams, Hybrid Cognito/TUSER Auth, and Feature-Flagged Billing

- **Status:** Accepted
- **Date:** 2026-11-10
- **Deciders:** Adam, Architecture Review Session

---

## Context

Our architectural scan of `api/` and `frontend/` identified five structural sources of friction and bugs:
1. **Duplicated Auth, Impersonation & Uncached Network Calls:** Every Lambda handler manually called `require_tenant_auth` or `get_user_role_in_tenant`. `cognito-idp.get_user()` and `secretsmanager.get_secret_value()` were called over the network on every request without caching. In `api/content_handler.py:602`, re-querying `get_user_role_in_tenant` bypassed the Superadmin `X-Impersonate-Tenant` check, causing `403 Forbidden` when a superadmin edited tenant content.
2. **Shallow DynamoDB Key Builders & `SITE#` Sort-Key Collision:** `api/dynamodb_helpers.py` exposed 35 shallow dict-building functions while leaving `table.query()` calls scattered across 11 handlers and duplicated in `api/admin_tenant_resources.py` (338 LOC). Because pages, posts, events, and media use sort keys `SITE#{site_id}#PAGE#...`, `query_sites_in_tenant` (`begins_with(sk, "SITE#")`) accidentally read every content item in the tenant partition on every `GET /api/tenant/sites` request. Meanwhile, `_decrement_storage` in `api/content_handler.py:184` called `greatest(...)`, an invalid DynamoDB function that crashed every media deletion with a 500 error.
3. **Triplicated Publish Pipelines & Relative Path Bugs:** `api/publish_handler.py` duplicated rendering across `_publish_site`, `_draft_publish_site`, and `_rollback_site`, hardcoding `/site/{tenant}/{site_id}/` links and injecting unsanitized HTML (`base_layout.py`).
4. **2,494-Line `frontend/src/lib/api.ts` & Dual-Token Collision:** 84 shallow `fetch` wrappers shared a global mutable `_impersonateTenant` variable (causing race conditions during React navigation) and conflated `access_token` (Cognito) with `site_token` (`TUSER`).
5. **MVP Billing Visibility:** Stripe billing stubs had two logic bugs (`not is_payable_tier("FREE")` blocked `FREE` tenants from upgrading; `stripe_webhook_handler.py` overwrote `VIP` tenants with `FREE`), and the user wants Billing UI hidden behind a feature flag for the MVP.

---

## Decision

1. **Preserve Hybrid Auth (`CognitoUser` + `TenantUser`) Behind a Deep `RequestContext` (`api/request_context.py`):**
   - Keep 100% of the AWS Cognito footprint for Tenant Admins and Superadmins (enabling MFA, Passkeys, and future 3rd-party OIDC/SAML IdPs) while preserving DynamoDB-backed `TUSER`, `ROLE`, and `GROUP` entities for flexible tenant-managed collaborators.
   - `RequestContext` verifies Cognito tokens locally against a module-cached JWKS (`cognito-idp` network call eliminated), verifies `TUSER` HMAC tokens against a module-cached secret, resolves `X-Impersonate-Tenant` once (setting effective role to `admin` for superadmins), enforces tier/module gates, serializes `Decimal` types, and strips stack traces from 500 responses.

2. **Introduce a Deep `TenantStore` Repository (`api/tenant_store.py`):**
   - Encapsulate all `9host-main` single-table operations behind `TenantStore` with `DynamoDBTenantStore` (prod) and `InMemoryTenantStore` (`pytest`).
   - Fix `list_sites(tenant_slug)` so it never scans `SITE#{id}#PAGE/POST/EVENT/MEDIA` items (by storing/indexing site metadata items with an attribute/prefix check and backfilling seamlessly).
   - Fix `adjust_storage_bytes(tenant_slug, delta_bytes)` using conditional atomic updates (`storage_used_bytes >= :abs_delta`, falling back to setting `0` on `ConditionalCheckFailedException`) instead of the invalid `greatest()` function.
   - Delete the duplicated CRUD in `api/admin_tenant_resources.py` by routing `/api/admin/tenants/{slug}/*` through the unified domain handlers with an admin-scoped `RequestContext`.

3. **Extract a Pure `SiteCompiler` (`api/site_compiler.py`) & `SiteStoragePort` (`api/site_storage.py`):**
   - `compile_site(snapshot: SiteSnapshot, mode: "live" | "draft") -> CompiledSiteBundle` is a pure function with zero AWS I/O.
   - Renders root-relative URLs (`/`, `/blog/`, `/events/`, `/media/...`) for live sites and sanitizes rich-text HTML against Stored XSS.
   - `SiteStoragePort` writes the compiled bundle to S3 (`published/v{N}/`, `published/current/`, `draft/`) and updates `HostMappingKVS`.

4. **Deepen Frontend `ApiClient` (`frontend/src/lib/api-client.ts`) & `TenantScope` (`frontend/src/context/tenant-scope.tsx`):**
   - Replace the 84 repetitive functions in `api.ts` with a resource-oriented `ApiClient` that cleanly separates Cognito `access_token` from `TUSER` `site_token` and passes `tenantSlug` / `impersonateTenant` per request.
   - Reuse one set of resource view components across both Tenant Dashboard (`/:tenantSlug/*`) and Superadmin Console (`/admin/tenants/:slug`).

5. **Feature-Flag Billing for MVP (`VITE_ENABLE_BILLING=false` / `BILLING_ENABLED=false`):**
   - Hide the Billing tab, pricing cards, and upgrade CTAs in the frontend when `VITE_ENABLE_BILLING !== "true"`.
   - Fix both backend Stripe bugs (`tenant.get("tier") == "VIP"` check in `api/billing_handler.py` and `api/stripe_webhook_handler.py`, plus `isBase64Encoded` webhook body decoding) and cover them with `pytest` unit tests so billing can be enabled anytime via configuration.

---

## Consequences

- **Positive:**
  - Every business rule (`RequestContext`, `TenantStore`, `SiteCompiler`, `Billing`, `EdgeHostRouter`) can be tested in milliseconds in `pytest` and `vitest` using `InMemoryTenantStore` and fake storage ports — critical for unattended AI agent execution.
  - Eliminates over 1,800 lines of duplicated handler and API wrapper boilerplate.
  - Resolves all 9 production bugs uncovered in the audit.
