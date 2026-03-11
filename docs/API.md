# 9host API

API Gateway HTTP API — all routes require `Authorization: Bearer <cognito_access_token>` unless noted.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/health | No | Health check |
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
| GET | /api/templates | Yes | List templates (tier-filtered; requires X-Tenant-Slug or subdomain) |
| GET | /api/admin/tenants | Yes | List all tenants (superadmin) |
| GET | /api/admin/tenants/{slug} | Yes | Get tenant (superadmin) |
| PATCH | /api/admin/tenants/{slug} | Yes | Update tenant tier/name/module_overrides (superadmin) |
| GET | /api/admin/templates | Yes | List all templates (superadmin) |
| POST | /api/admin/tenants | Yes | Create tenant (superadmin). Body: slug, name, tier. |
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
