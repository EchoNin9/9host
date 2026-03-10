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
