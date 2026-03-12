# 9host API

API Gateway HTTP API — routes require `Authorization: Bearer <token>` (Cognito or custom JWT) unless noted.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/health | No | Health check |
| POST | /api/auth/site-login | No | Non-Cognito tenant user login. Body: username, password, site (tenant_slug). Returns token. |
| GET | /api/tenants | Yes | List tenants for authenticated user |
| GET | /api/tenant | Yes | Tenant metadata (requires X-Tenant-Slug or subdomain) |
| GET | /api/tenant/analytics | Yes | Analytics placeholder (Pro+ tier; requires X-Tenant-Slug or subdomain) |
| GET | /api/tenant/sites | Yes | List sites (requires X-Tenant-Slug or subdomain) |
| POST | /api/tenant/sites | Yes | Create site |
| GET | /api/tenant/sites/{id} | Yes | Get site |
| PUT | /api/tenant/sites/{id} | Yes | Update site |
| DELETE | /api/tenant/sites/{id} | Yes | Delete site |
| GET | /api/tenant/domains | Yes | List domains (Pro+; requires X-Tenant-Slug or subdomain) |
| POST | /api/tenant/domains | Yes | Add domain |
| GET | /api/tenant/domains/{domain} | Yes | Get domain |
| DELETE | /api/tenant/domains/{domain} | Yes | Remove domain |
| GET | /api/tenant/users | Yes | List Cognito users (admin/manager) |
| GET | /api/tenant/users/{sub}/permissions | Yes | Get/put user permissions |
| GET | /api/tenant/tusers | Yes | List non-Cognito tenant users (admin/manager) |
| POST | /api/tenant/tusers | Yes | Create non-Cognito user. Body: username, password, display_name, role. |
| PUT | /api/tenant/tusers/{username} | Yes | Update non-Cognito user |
| DELETE | /api/tenant/tusers/{username} | Yes | Delete non-Cognito user |
| GET | /api/tenant/roles | Yes | List custom roles (admin/manager) |
| POST | /api/tenant/roles | Yes | Create custom role. Body: name, permissions. |
| PUT | /api/tenant/roles/{name} | Yes | Update custom role permissions |
| DELETE | /api/tenant/roles/{name} | Yes | Delete custom role (fail if users assigned) |
| GET | /api/templates | Yes | List templates (tier-filtered; requires X-Tenant-Slug or subdomain) |
| POST | /api/tenant/billing/checkout | Yes | Create Stripe Checkout Session for subscription (admin/manager) |
| POST | /api/tenant/billing/portal | Yes | Create Stripe Customer Portal session (admin/manager) |
| POST | /api/webhooks/stripe | No | Stripe webhook (signature-verified) |
| GET | /api/admin/tenants | Yes | List all tenants (superadmin) |
| GET | /api/admin/tenants/{slug} | Yes | Get tenant (superadmin) |
| PATCH | /api/admin/tenants/{slug} | Yes | Update tenant tier/name/module_overrides (superadmin) |
| GET | /api/admin/templates | Yes | List all templates (superadmin) |
| POST | /api/admin/tenants | Yes | Create tenant (superadmin). Body: slug, name, tier. |
| DELETE | /api/admin/tenants/{slug} | Yes | Delete tenant + cascade (superadmin) |
| GET | /api/admin/tenants/{slug}/domains | Yes | List domains (superadmin) |
| POST | /api/admin/tenants/{slug}/domains | Yes | Add domain (superadmin). Body: domain, site_id. |
| DELETE | /api/admin/tenants/{slug}/domains/{domain} | Yes | Remove domain (superadmin) |
| GET | /api/admin/tenants/{slug}/sites | Yes | List sites (superadmin) |
| POST | /api/admin/tenants/{slug}/sites | Yes | Create site (superadmin). Body: name, slug?, template_id? |
| GET | /api/admin/tenants/{slug}/sites/{id} | Yes | Get site (superadmin) |
| PUT | /api/admin/tenants/{slug}/sites/{id} | Yes | Update site (superadmin) |
| DELETE | /api/admin/tenants/{slug}/sites/{id} | Yes | Delete site (superadmin) |
| GET | /api/admin/tenants/{slug}/users | Yes | List users (superadmin) |
| POST | /api/admin/tenants/{slug}/users | Yes | Add user (superadmin). Body: sub, role?, email?, name? |
| PUT | /api/admin/tenants/{slug}/users/{sub} | Yes | Update user role/email/name (superadmin) |
| DELETE | /api/admin/tenants/{slug}/users/{sub} | Yes | Remove user (superadmin) |
| GET | /api/admin/tenants/{slug}/users/{sub}/permissions | Yes | Get user permissions (superadmin) |
| PUT | /api/admin/tenants/{slug}/users/{sub}/permissions | Yes | Update user permissions (superadmin) |
| PUT | /api/admin/tenants/{slug}/settings | Yes | Update tenant settings (superadmin). Body: tier?, name?, module_overrides?, owner_sub? |
| GET | /api/admin/templates | Yes | List all templates (superadmin) |
| POST | /api/admin/templates | Yes | Create template (superadmin) |
| GET | /api/admin/templates/{slug} | Yes | Get template (superadmin) |
| PUT | /api/admin/templates/{slug} | Yes | Update template (superadmin) |
| DELETE | /api/admin/templates/{slug} | Yes | Delete template (superadmin) |

## GET /api/tenant/analytics

**Requirements:** Cognito auth, tenant membership, tenant tier Pro or Business.

**Request:** Call from tenant subdomain (e.g. `acme.echo9.net`) or with `X-Tenant-Slug: acme`.

**Response (200):**
```json
{
  "period": "last_30_days",
  "page_views_over_time": [{"date": "2025-02-08", "count": 120}, ...],
  "total_page_views": 4500,
  "unique_visitors": 420,
  "top_pages": [{"path": "/", "views": 1250}, ...],
  "placeholder": true
}
```

**403 (Pro required):** `{"error": "Advanced Analytics requires Pro or Business tier.", "tier": "FREE", "upgrade_required": true}`

## Sites API (/api/tenant/sites)

**Requirements:** Cognito auth, tenant membership (X-Tenant-Slug or subdomain).

**GET /api/tenant/sites** — List sites. Response: `{"sites": [{"id", "name", "slug", "status", "created_at", "updated_at"}, ...]}`

**POST /api/tenant/sites** — Create site. Body: `{"name": "My Site", "slug": "my-site", "status": "draft"}`. slug optional (auto from name). status: draft | published.

**GET /api/tenant/sites/{id}** — Get site. Response: `{"site": {...}}`

**PUT /api/tenant/sites/{id}** — Update site. Body: `{"name", "slug", "status"}` (all optional).

**DELETE /api/tenant/sites/{id}** — Delete site. 204 No Content.

## Domains API (/api/tenant/domains)

**Requirements:** Cognito auth, tenant membership, tenant tier Pro or Business (X-Tenant-Slug or subdomain).

**GET /api/tenant/domains** — List domains. Response: `{"domains": [{"domain", "site_id", "status", "created_at", "updated_at"}, ...]}`

**POST /api/tenant/domains** — Add domain. Body: `{"domain": "example.com", "site_id": "uuid", "status": "pending"}`. domain and site_id required. status: pending | verified.

**GET /api/tenant/domains/{domain}** — Get domain. Response: `{"domain": {...}}`

**DELETE /api/tenant/domains/{domain}** — Remove domain. 204 No Content.

**403 (Pro required):** `{"error": "Custom Domains requires Pro or Business tier.", "tier": "FREE", "upgrade_required": true}`
