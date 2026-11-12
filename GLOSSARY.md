# 9host — Domain Glossary

Canonical ubiquitous language for the 9host multi-tenant website hosting platform. Code, database keys, infrastructure resources, and documentation must use these exact terms.

---

## Core Domain Entities

### Tenant
An isolated customer account identified by a unique, immutable `tenant_slug` (e.g., `echo9`, `acme`). Stored in DynamoDB under partition key `PK = TENANT#{tenant_slug}`, `SK = METADATA`. Holds the subscription `tier` (`FREE`, `PRO`, `BUSINESS`, `VIP`), `storage_used_bytes`, `module_overrides`, and `owner_sub`.

### Site
A website belonging to a `Tenant`, identified by `site_id` (UUID) and a globally unique `site_slug` (e.g., `jinks1` -> `jinks1.echo9.net`). Stored in DynamoDB and compiled into static HTML assets in S3 (`9host-sites`) under `{tenant_slug}/{site_id}/`.

### CustomHostname
A tenant-owned external domain (e.g., `myband.com` or `www.myband.com`) bound to a specific `Site`. Provisioned and SSL-terminated via **Cloudflare for SaaS** on the `echo9.net` zone (`CNAME -> proxy.echonin9.com`), forwarded to the 9host Public Sites CloudFront distribution with `X-Forwarded-Host`, and mapped to `{tenant_slug}/{site_id}` in `HostMappingKVS`.

---

## Identity & Access Management (Hybrid Auth)

### Principal
The authenticated caller inside a `RequestContext`. Always one of two concrete types:
1. **`CognitoUser` (`USER#{sub}`)**: Account owners, Tenant Admins, and platform Superadmins authenticated via the AWS Cognito User Pool (`9host-user-pool`). Supports MFA, Passkeys, and future 3rd-party OIDC/SAML IdP federation.
2. **`TenantUser` (`TUSER#{username}`)**: Lightweight site collaborators created and managed directly by a Tenant Admin inside DynamoDB (`PK = TENANT#{slug}`, `SK = TUSER#{username}`), authenticated via `/api/auth/site-login` using a tenant-scoped HMAC-SHA256 JWT (`site_token`).

### Role & CustomRole
Built-in roles (`admin`, `manager`, `editor`, `member`) or tenant-defined `CustomRole` entities (`PK = TENANT#{slug}`, `SK = ROLE#{name}`) granting granular module and content permissions within a `Tenant`.

### ImpersonationSession
A Superadmin-only capability triggered via the `X-Impersonate-Tenant: {tenant_slug}` HTTP header. Resolved once inside `RequestContext`, granting effective `admin` role in the target `Tenant` without mutating global frontend state.

---

## Deep Module Boundaries (The 5 Seams)

### 1. EdgeHostRouter (`infra/cf-site-content.js` + `HostMappingKVS`)
The CloudFront viewer-request function on the Public Sites distribution (`*.echo9.net`). Reads the effective hostname (`x-forwarded-host` when verified from the Cloudflare SaaS proxy, otherwise `host`), looks up `{tenant_slug}/{site_id}` in **CloudFront KeyValueStore (`HostMappingKVS`)** in $O(1)$ time, and rewrites the S3 URI to `/{tenant_slug}/{site_id}/published/current/...` directly at `/`.

### 2. RequestContext (`api/request_context.py`)
The deep ingress module for all Lambda API invocations. Encapsulates:
- Local Cognito JWT verification via cached JWKS (`cognito_jwks_cache`) and `TenantUser` HMAC-SHA256 JWT verification.
- Superadmin `ImpersonationSession` resolution.
- Single-read tenant membership, role, and tier feature-gate enforcement.
- Safe JSON response serialization (`Decimal` conversion, CORS headers, and sanitized 500 error responses that never leak Python tracebacks).

### 3. TenantStore (`api/tenant_store.py`)
The deep repository module hiding all DynamoDB single-table (`9host-main`) key construction, GSI queries (`byUser`, `byDomain`, `bySiteSlug`, `byEntity`), atomic storage-quota accounting (`adjust_storage_bytes`), and tenant partition isolation (`PK = TENANT#{slug}`). Exposes a clean protocol with two implementations:
- `DynamoDBTenantStore` (production AWS adapter)
- `InMemoryTenantStore` (fast, zero-AWS `pytest` adapter)

### 4. SiteCompiler (`api/site_compiler.py`) & SiteStoragePort (`api/site_storage.py`)
- **`SiteCompiler`**: Pure, deterministic in-process module (`compile_site(snapshot, mode) -> CompiledSiteBundle`) that sanitizes rich-text HTML against XSS and renders all template pages, blog posts, events, and media galleries using clean root-relative URLs (`/`, `/blog/`, `/events/`, `/media/...`).
- **`SiteStoragePort`**: Adapter responsible for uploading a `CompiledSiteBundle` to S3 (`published/v{N}/` + `published/current/` or `draft/`), updating `current.json`, and syncing `HostMappingKVS`.

### 5. ApiClient (`frontend/src/lib/api-client.ts`) & TenantScope (`frontend/src/context/tenant-scope.tsx`)
- **`ApiClient`**: Deep frontend HTTP transport replacing the 84 shallow wrapper functions in `api.ts`. Separates `cognito_access_token` from `site_token` and attaches explicit per-request tenant and impersonation headers.
- **`TenantScope`**: React context (`useTenantScope()`) shared by both the Tenant Dashboard (`/:tenantSlug/*`) and Superadmin Console (`/admin/tenants/:slug`), allowing one set of resource views (`SitesView`, `PagesView`, `PostsView`, `EventsView`, `MediaView`, `DomainsView`, `UsersView`, `SettingsView`) to serve both shells.

---

## Feature Flags

### BillingFeatureFlag (`VITE_ENABLE_BILLING` / `BILLING_ENABLED`)
Boolean flag (default `false` in MVP) that hides the Billing tab, pricing tier cards, and upgrade CTAs in the frontend UI while keeping the underlying Stripe Checkout and Webhook handlers tested and ready to enable when set to `true`.
