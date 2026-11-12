# 9host — Architectural Overhaul & Deep-Module Technical Specification

> **References:** [`GLOSSARY.md`](../GLOSSARY.md) · [`ADR-0001`](adr/0001-edge-routing-split-and-cloudflare-for-saas.md) · [`ADR-0002`](adr/0002-deep-module-seams-and-hybrid-auth.md) · [`docs/UNATTENDED_ORCHESTRATION.md`](UNATTENDED_ORCHESTRATION.md)

---

## 1. Problem Statement

9host currently works for basic happy-path testing, but suffers from nine architectural and implementation defects that prevent reliable custom domain hosting, fast public site viewing, and low-cost operations:

1. **Public Site Visits Boot the React Admin SPA (`App.tsx:RootRoute` + `api/default_site_handler.py`):** Visiting `https://<slug>.echo9.net/` downloads the React Admin SPA, executes a Lambda + DynamoDB lookup (`GET /api/tenant/default-site`), and redirects the visitor to `/site/{tenant}/{site_id}/`.
2. **Broken Per-Domain ACM Certificate Flow (`infra/cloudfront.tf:452` + `api/custom_domain_handler.py`):** CloudFront only attaches one ACM certificate (`*.echo9.net`) per distribution. Attempting to attach per-domain ACM certificates or aliases fails or triggers `SSL_ERROR_BAD_CERT_DOMAIN`. Furthermore, `CLOUDFRONT_SITES_DISTRIBUTION_ID` and `cloudfront:*` IAM permissions are missing on `9host-api`, and `tofu apply` overwrites `aliases`.
3. **Full-Tenant Content Scan on Site Listing (`api/dynamodb_helpers.py:258`):** `query_sites_in_tenant` queries `pk = TENANT#{slug} AND begins_with(sk, "SITE#")`, which reads every `SITE#{id}#PAGE#...`, `POST#...`, `EVENT#...`, and `MEDIA#...` record in the tenant partition on every `GET /api/tenant/sites` call.
4. **Media Deletion 500 Crash (`api/content_handler.py:184`):** `_decrement_storage()` uses `greatest(...)` in a DynamoDB `UpdateExpression`, which is not a valid DynamoDB function (`ValidationException`).
5. **Superadmin Impersonation 403 on Content Editing (`api/content_handler.py:602`):** `content_handler` ignores the role returned by `require_tenant_auth` and re-queries `get_user_role_in_tenant()`, which lacks the `X-Impersonate-Tenant` check.
6. **Stripe Billing Bugs (`api/billing_handler.py:85` + `api/stripe_webhook_handler.py:106`):** `not is_payable_tier("FREE")` blocks `FREE` tenants from upgrading; non-active webhook events overwrite `VIP` tenants with `FREE` and fail on base64-encoded API Gateway payloads.
7. **Uncached Network Calls on Every Request (`api/auth_helpers.py:40` + `api/stripe_helpers.py:18`):** Every authenticated API call invokes `cognito-idp.get_user()` and `secretsmanager.get_secret_value()` over the network.
8. **Security Vulnerabilities (`api/handler.py:252`, `infra/cf-preview-content.js`, `api/templates/base_layout.py`):** 500 responses return raw Python stack traces (`detail.traceback`); `cf-preview-content.js` decodes the draft preview JWT without verifying the HMAC-SHA256 signature; rich-text HTML is injected without server-side sanitization.
9. **S3 Noncurrent Version Bloat & Vendored Wheels in Git (`infra/s3.tf:107`, `api/`):** `9host-sites` and `9host-media` have versioning enabled with no noncurrent version expiration lifecycle policy; third-party pip packages (`stripe/`, `jwt/`, `bcrypt/`, `requests/`, `urllib3/`, `idna/`, `certifi/`, `charset_normalizer/`) are committed directly inside `api/`.

---

## 2. Target Architecture & User Stories

### User Stories
- **US-01 (Subdomain Site Viewing at `/`):** As a site visitor navigating to `https://<site-slug>.echo9.net/`, I immediately receive the static HTML of the site at `/` (with clean `/`, `/blog/`, `/events/`, `/media/...` links) in $<10\text{ ms}$ from CloudFront + S3 without loading the React Admin SPA or invoking Lambda/DynamoDB.
- **US-02 (Landing Page at `(www.)echo9.net`):** As a visitor to `https://echo9.net` or `https://www.echo9.net`, I see the 9host landing page instead of redirecting to `tools.e9.cx`.
- **US-03 (Admin SPA on `app.echo9.net` / `stage.echo9.net`):** As a Tenant Admin, Superadmin, or `TUSER` collaborator, I log into `https://app.echo9.net` (production) or `https://stage.echo9.net` (staging) to manage sites, content, domains, and users.
- **US-04 (Custom Domains via Cloudflare for SaaS — Option B2):** As a Tenant Admin adding `myband.com` from ClouDNS or any registrar, I add a single `CNAME -> proxy.echonin9.com` (and TXT validation record if apex). Cloudflare automatically issues the SSL certificate and routes traffic through the fallback Worker to my 9host site at `https://myband.com/`.
- **US-05 (Hybrid Cognito + `TUSER` Auth & Impersonation):** As a Tenant Admin authenticated via AWS Cognito, I can manage non-Cognito `TUSER` collaborators, custom `ROLE`s, and `GROUP`s; as a Superadmin impersonating a tenant, I can create, edit, and delete any site or content item without 403 errors.
- **US-06 (Feature-Flagged Billing in MVP):** When `VITE_ENABLE_BILLING=false` (default for MVP), all billing tabs, pricing cards, and upgrade banners are hidden in the UI, while backend Stripe Checkout and Webhook logic is fixed and verified by unit tests so setting `VITE_ENABLE_BILLING=true` enables SaaS billing cleanly.

---

## 3. Deep Module Interfaces & Seams

### Module 1: `EdgeHostRouter` (`infra/cf-site-content.js` + `HostMappingKVS` + Cloudflare Worker)

#### 1A. CloudFront Distribution Split (`infra/cloudfront.tf`)
- **`aws_cloudfront_distribution.frontend` (Admin SPA):**
  - Production aliases: `["app.echo9.net", "app.echo9.ca"]` (plus `prod.echo9.net` for backwards compatibility during cutover).
  - Staging aliases: `["stage.echo9.net", "stage.echo9.ca"]`.
  - Default origin (`/*`): `S3-9host-frontend-{env}` with `cf-spa-routing.js`.
  - `/api/*` behavior: API Gateway (`9host-api`).
- **`aws_cloudfront_distribution.sites` (Public Sites & Landing Page):**
  - Aliases: `["*.echo9.net", "*.echo9.ca", "echo9.net", "www.echo9.net"]`.
  - Default origin (`/*`): `S3-9host-sites` (with OAC).
  - Viewer-request function on default behavior (`/*`): `cf-site-content.js` bound to `aws_cloudfront_key_value_store.site_hosts` (`9host-site-hosts-kvs`).
  - `/media/*` behavior: `S3-9host-media` with `cf-media-content.js`.
  - `/preview*` behavior: `S3-9host-sites` with `cf-preview-content.js` (updated to verify HMAC-SHA256 signature via `crypto.subtle`).

#### 1B. CloudFront KeyValueStore Schema (`9host-site-hosts-kvs`)
- Keys are lowercase hostnames:
  - Subdomain: `"jinks1.echo9.net"` -> `'{"tenant":"echo9","site_id":"a1b2c3d4"}'`
  - Custom domain: `"myband.com"` -> `'{"tenant":"echo9","site_id":"a1b2c3d4"}'`
  - Bare landing domain: `"echo9.net"` / `"www.echo9.net"` -> `'{"tenant":"echo9","site_id":"<landing_site_id>"}'`

#### 1C. `infra/cf-site-content.js` (`cloudfront-js-2.0`)
```javascript
import cf from 'cloudfront';

var kvsHandle = null;
try {
    kvsHandle = cf.kvs();
} catch (e) {}

async function handler(event) {
    var request = event.request;
    var headers = request.headers;
    var uri = request.uri || '/';

    // 1. Backwards-compatible explicit /site/{tenant}/{site_id}/... path
    var siteMatch = uri.match(/^\/site\/([a-z0-9_-]+)\/([a-zA-Z0-9_-]+)(\/.*)?$/);
    if (siteMatch) {
        var tSlug = siteMatch[1];
        var sId = siteMatch[2];
        var rest = siteMatch[3] || '/index.html';
        if (rest.endsWith('/')) rest = rest + 'index.html';
        else if (rest.indexOf('.') === -1) rest = rest + '/index.html';
        request.uri = '/' + tSlug + '/' + sId + '/published/current' + rest;
        return request;
    }

    // 2. Determine effective hostname (X-Forwarded-Host from Cloudflare SaaS Worker or Host)
    var host = (headers[' host'] && headers['host'].value) ? headers['host'].value.toLowerCase().split(':')[0] : '';
    var fwdHost = (headers['x-forwarded-host'] && headers['x-forwarded-host'].value)
        ? headers['x-forwarded-host'].value.toLowerCase().split(',')[0].trim()
        : '';
    var effectiveHost = fwdHost || host;

    // 3. Resolve {tenant, site_id} via CloudFront KeyValueStore
    if (kvsHandle && effectiveHost) {
        try {
            var raw = await kvsHandle.get(effectiveHost);
            if (raw) {
                var mapping = JSON.parse(raw);
                var subPath = uri;
                if (subPath === '' || subPath === '/') {
                    subPath = '/index.html';
                } else if (subPath.endsWith('/')) {
                    subPath = subPath + 'index.html';
                } else if (subPath.indexOf('.') === -1) {
                    subPath = subPath + '/index.html';
                }
                request.uri = '/' + mapping.tenant + '/' + mapping.site_id + '/published/current' + subPath;
                return request;
            }
        } catch (err) {}
    }

    return request;
}
```

#### 1D. Cloudflare for SaaS Fallback Worker (`infra/cloudflare-worker/custom-domain-proxy.js`)
Deployed on the `echo9.net` Cloudflare zone (`proxy.echonin9.com/*` and `*/*` custom hostname fallback route):
```javascript
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const originHost = env.SITES_ORIGIN_HOST || "sites-origin.echo9.net";
    const targetUrl = `https://${originHost}${url.pathname}${url.search}`;
    const headers = new Headers(request.headers);
    headers.set("X-Forwarded-Host", url.hostname);
    return fetch(targetUrl, {
      method: request.method,
      headers,
      redirect: "manual",
    });
  },
};
```

#### 1E. `CloudflareSaaSAdapter` (`api/cloudflare_saas.py`)
Replaces all AWS ACM calls in `api/custom_domain_handler.py` and deletes `infra/lambda_acm.tf` + `infra/lambda_acm_handler/`:
```python
class CustomDomainPort(Protocol):
    def register_hostname(self, domain: str) -> CustomHostnameRecord: ...
    def get_hostname_status(self, cf_hostname_id: str) -> CustomHostnameRecord: ...
    def delete_hostname(self, cf_hostname_id: str) -> None: ...
```
- Uses `9host-cloudflare` secret (`zone_id`, `api_token`) to call Cloudflare Custom Hostnames API (`https://api.cloudflare.com/client/v4/zones/{zone_id}/custom_hostnames`).
- When status reaches `active`, updates DynamoDB domain status to `ACTIVE` and writes `domain -> {tenant, site_id}` into `HostMappingKVS`.

---

### Module 2: `RequestContext` (`api/request_context.py`)

Single ingress gate replacing scattered `auth_helpers.py` and `middleware.py` boilerplate:
```python
@dataclass(frozen=True)
class Principal:
    kind: Literal["cognito", "tuser"]
    identifier: str          # Cognito sub or TUSER username
    email: str | None
    is_superadmin: bool
    token_tenant_slug: str | None = None
    token_role: str | None = None

@dataclass(frozen=True)
class RequestContext:
    event: dict
    principal: Principal | None
    tenant_slug: str | None
    effective_role: str | None      # "admin" | "manager" | "editor" | "member" | custom role
    is_impersonating: bool
    tenant_item: dict | None        # Cached tenant METADATA row when loaded

    def require_authenticated(self) -> Principal: ...
    def require_superadmin(self) -> Principal: ...
    def require_tenant_member(self, min_roles: tuple[str, ...] | None = None) -> tuple[str, str]: ...
    def require_feature(self, feature_key: str) -> None: ...
```
- **Local Cognito JWT Verification:** Uses `jwt` (`PyJWT`) + module-cached Cognito JWKS (`https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json`, 1-hour TTL) instead of calling `cognito-idp.get_user()` on every request.
- **Module-Level Secret Cache:** Caches `9host-jwt-secret`, `9host-stripe`, `9host-cloudns`, and `9host-cloudflare` in memory with 5-minute TTL.
- **Impersonation Fix (`Bug #5`):** When `principal.is_superadmin` and `X-Impersonate-Tenant` (or `/api/admin/tenants/{slug}/*` path) is present, `effective_role` is set to `"admin"` once on `RequestContext`. No handler ever calls `get_user_role_in_tenant` directly.
- **Safe Error & Decimal Serialization (`Bug #8`):** `run_with_context(event, handler_fn)` converts `Decimal` -> `int | float`, applies CORS headers, logs full exceptions to CloudWatch, and returns `{"error": "Internal server error", "request_id": "..."}` on unhandled 500s (never leaking `traceback`).

---

### Module 3: `TenantStore` (`api/tenant_store.py`)

Deep repository interface hiding all DynamoDB single-table (`9host-main`) key formatting and GSI queries:
```python
class TenantStore(Protocol):
    # Tenant metadata & storage quota
    def get_tenant(self, tenant_slug: str) -> dict | None: ...
    def update_tenant(self, tenant_slug: str, updates: dict) -> dict: ...
    def adjust_storage_bytes(self, tenant_slug: str, delta_bytes: int) -> int: ...

    # Sites (fixes Bug #3: never scans PAGE/POST/EVENT/MEDIA items)
    def list_sites(self, tenant_slug: str) -> list[dict]: ...
    def get_site(self, tenant_slug: str, site_id: str) -> dict | None: ...
    def put_site(self, tenant_slug: str, site: dict) -> dict: ...
    def delete_site_cascade(self, tenant_slug: str, site_id: str) -> None: ...
    def resolve_site_slug(self, site_slug: str) -> dict | None: ...

    # Content (PAGE, POST, EVENT, MEDIA)
    def list_content(self, tenant_slug: str, site_id: str, content_type: str, status: str | None = None) -> list[dict]: ...
    def get_content(self, tenant_slug: str, site_id: str, content_type: str, item_id: str) -> dict | None: ...
    def put_content(self, tenant_slug: str, site_id: str, content_type: str, item: dict) -> dict: ...
    def delete_content(self, tenant_slug: str, site_id: str, content_type: str, item_id: str) -> dict | None: ...

    # Hybrid Auth Entities (USER, TUSER, ROLE, PERMISSIONS)
    def get_member_role(self, tenant_slug: str, sub: str) -> str | None: ...
    def list_cognito_members(self, tenant_slug: str) -> list[dict]: ...
    def list_tusers(self, tenant_slug: str) -> list[dict]: ...
    def list_roles(self, tenant_slug: str) -> list[dict]: ...
```
- **Fixing `Bug #3` (`SITE#` Sort-Key Collision):**
  - Site metadata items are written to `SK = SITE_META#{site_id}` **and** mirrored to `SK = SITE#{site_id}` during expand-contract migration (or `list_sites` queries `SK begins_with("SITE_META#")` with automatic lazy backfill from `SITE#{id}` where `entity_type == "SITE"`), guaranteeing $O(\text{sites})$ reads instead of $O(\text{all content})$.
- **Fixing `Bug #4` (`greatest()` Media Delete Crash):**
  - `adjust_storage_bytes(tenant_slug, delta_bytes)`:
    - When `delta_bytes >= 0`: `ADD storage_used_bytes :delta`.
    - When `delta_bytes < 0`: `SET storage_used_bytes = storage_used_bytes - :abs_delta` with `ConditionExpression="storage_used_bytes >= :abs_delta"`. If `ConditionalCheckFailedException` is raised, sets `storage_used_bytes = :zero`.
- **Unified Admin/Tenant CRUD:**
  - Deletes the 338-line duplicated logic in `api/admin_tenant_resources.py` by delegating `/api/admin/tenants/{slug}/{sites|domains|users|settings}` to the standard handlers using an admin-scoped `RequestContext`.

---

### Module 4: `SiteCompiler` (`api/site_compiler.py`) & `SiteStoragePort` (`api/site_storage.py`)

```python
@dataclass(frozen=True)
class SiteSnapshot:
    tenant_slug: str
    site_id: str
    site: dict
    template: dict
    pages: list[dict]
    posts: list[dict]
    events: list[dict]
    media: list[dict]

@dataclass(frozen=True)
class CompiledSiteBundle:
    files: dict[str, bytes]        # relative path (e.g. "index.html", "blog/index.html") -> UTF-8 bytes
    content_types: dict[str, str]  # relative path -> MIME type
    manifest: dict

def compile_site(snapshot: SiteSnapshot, mode: Literal["live", "draft"] = "live") -> CompiledSiteBundle:
    ...
```
- **Root-Relative URLs:** When `mode == "live"`, `base_path` is `""` so all internal navigation links render as `/`, `/blog/`, `/posts/{slug}/`, `/events/`, `/gallery/` instead of `/site/{tenant}/{site_id}/`. When `mode == "draft"`, `base_path` is `/preview`.
- **HTML Sanitization (`Bug #8`):** Sanitizes rich-text body HTML via an allowlist sanitizer (`api/html_sanitizer.py`) stripping `<script>`, `<iframe>`, `<object>`, `javascript:` URLs, and `on*` event handler attributes while preserving semantic formatting tags.
- **Atomic Storage & KVS Sync (`SiteStoragePort`):**
  - Uploads `CompiledSiteBundle.files` to `s3://9host-sites/{tenant}/{site_id}/published/v{N}/` and `published/current/`.
  - Updates `{tenant}/{site_id}/published/current.json`.
  - Updates `HostMappingKVS` (`{site_slug}.echo9.net` -> `{"tenant": tenant_slug, "site_id": site_id}` and all `ACTIVE` custom domains for that site).

---

### Module 5: Frontend `ApiClient` (`frontend/src/lib/api-client.ts`), `TenantScope`, & Billing Flag

1. **Scoped `ApiClient`:**
   - Replaces the 84 repetitive functions in `frontend/src/lib/api.ts` with a typed resource client (`apiClient.forTenant(tenantSlug, { impersonate })`).
   - Keeps `frontend/src/lib/api.ts` as a thin compatibility re-export layer during migration so existing imports never break.
   - Cleanly separates `localStorage.getItem("9host_cognito_token")` (Cognito sessions) from `localStorage.getItem("9host_site_token")` (`TUSER` sessions) based on active auth mode, eliminating the dual-token collision.
2. **Shared Resource Views (`TenantScopeProvider`):**
   - `administer-tenant.tsx` wraps the existing tenant resource components (`tenant-sites.tsx`, `tenant-domains.tsx`, `tenant-users.tsx`, `tenant-settings.tsx`, `site-content-editor.tsx`) in `<TenantScopeProvider tenantSlug={slug} isSuperadminImpersonating={true}>`, eliminating ~700 lines of duplicated admin table/dialog code.
3. **Delete `RootRoute` Visitor Redirect & Gate Edge/Domains Health Behind Superadmin:**
   - In `frontend/src/App.tsx`, `/` routes directly to the Admin Dashboard / Login page on `app.echo9.net` / `stage.echo9.net`. `RootRoute` and `fetchDefaultSite` are removed.
   - **Public Landing Security Rule:** The public `(www.)echo9.net` landing page must **never** expose tenant domains, active subdomains, or CloudFront KVS routing entries.
   - **Superadmin-Gated Edge & Domains Health Panel:** The Live Edge Routing Table & Domains Health panel (`9host-site-hosts-kvs` + ClouDNS / Cloudflare for SaaS status across tenants) lives exclusively in the Superadmin Console (`/admin`) backed by `GET /api/admin/edge-kvs` (`ctx.require_superadmin()`).
4. **Billing Feature Flag (`VITE_ENABLE_BILLING`):**
   - Add `export const BILLING_ENABLED = import.meta.env.VITE_ENABLE_BILLING === "true";` in `frontend/src/lib/feature-flags.ts` (default `false`).
   - Hide the Billing tab/card in `tenant-settings.tsx` and upgrade banners in `FeatureGate.tsx` when `BILLING_ENABLED` is `false`.

---

## 4. Infrastructure, Packaging & Test Suite Requirements

1. **S3 Noncurrent Version Expiration (`infra/s3.tf`):**
   - Add `aws_s3_bucket_lifecycle_configuration` for `9host-sites` and `9host-media` expiring noncurrent object versions after `7` days and aborting incomplete multipart uploads after `1` day.
2. **Remove Vendored Packages from `api/` Source Tree:**
   - Add `api/build_lambda.sh` (and wire into `infra/lambda.tf` / GitHub Actions) that installs `api/requirements.txt` into `.build/lambda_api/` and copies `api/*.py` and `api/templates/`, then remove the committed third-party directories (`api/stripe/`, `api/jwt/`, `api/bcrypt/`, `api/requests/`, `api/urllib3/`, `api/idna/`, `api/certifi/`, `api/charset_normalizer/`, `api/*.dist-info`) from git.
3. **Automated Test Suites (`pytest` & `vitest`):**
   - **`api/tests/` (`pytest`):**
     - `test_request_context.py`: Local JWKS verification, `TUSER` JWT verification, Superadmin `X-Impersonate-Tenant` role resolution (`Bug #5`), and sanitized 500 error boundary (`Bug #8`).
     - `test_tenant_store.py`: `InMemoryTenantStore` & `DynamoDBTenantStore` sort-key isolation (`Bug #3`), `adjust_storage_bytes` floor at `0` (`Bug #4`), and tenant partition enforcement.
     - `test_site_compiler.py`: Pure `compile_site` output for all 5 templates, root-relative `/` links, and Stored XSS HTML sanitization (`Bug #8`).
     - `test_billing_and_webhooks.py`: `FREE` tenant checkout allowed (`Bug #6`), `VIP` tenant protected from checkout and from webhook downgrade (`Bug #6`), and `isBase64Encoded` payload handling.
     - `test_cloudflare_saas.py`: Custom domain registration, status polling, and `HostMappingKVS` sync.
   - **`frontend/src/__tests__/` (`vitest`):**
     - `api-client.test.ts`: Separate Cognito vs. `TUSER` token selection, explicit `X-Impersonate-Tenant` header scoping without global race state.
     - `feature-flags.test.tsx`: Billing UI hidden when `VITE_ENABLE_BILLING=false` and shown when `VITE_ENABLE_BILLING=true`.
