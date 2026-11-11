# 9host — Claude Code Guidelines

## Project Overview

Multi-tenant SaaS website hosting platform. Tenants get subdomains at `<slug>.echo9.net` with published static sites, admin dashboard, custom domains, and module-based content (blog, events, media gallery, branding).

## Architecture

- **Frontend:** React 19 + React Router 7 + Vite + Tailwind CSS + shadcn/ui
- **Backend:** Python Lambda (API Gateway HTTP API v2 proxy), DynamoDB single-table design
- **Infrastructure:** OpenTofu (IaC), AWS (CloudFront, S3, Lambda, DynamoDB, Cognito, ACM)
- **CI/CD:** GitHub Actions → OpenTofu apply → S3 sync → CloudFront invalidation

## Standards

### IaC
- Use **OpenTofu** (`tofu` CLI). Terraform OSS is no longer updated.
- All AWS resources MUST use the prefix `9host` (e.g. `9host-sites`, `9host-api`).

### Tenant Isolation
- Every DynamoDB query MUST use a Partition Key starting with `TENANT#`. Never perform cross-tenant lookups without explicit admin bypass.
- Backend middleware (`api/middleware.py`) extracts tenant from X-Tenant-Slug header, Host subdomain, or path param.

### Feature Gating
- Wrap premium frontend components in `<FeatureGate feature="custom_domains">` or `<FeatureGate feature="advanced_analytics">` (Pro+ tier).
- Backend uses `tier_config.py` for feature/module resolution per tier.

### Lambda / Backend
- Use AWS SDK v3 (boto3). Validate inputs; return structured JSON responses.
- All handlers return `{"statusCode": N, "headers": {...}, "body": "..."}`.
- CORS headers applied via `_with_cors()` wrapper in `handler.py`.

### CloudFront Functions
- Runtime: `cloudfront-js-2.0` (ES5-like, no ES6+ features). `async`/`await` is used only for KeyValueStore reads.
- Must be pure functions — no external calls, no sub-requests.

## Testing

- **Backend (Pytest):**
  ```bash
  cd api && ../.venv/bin/pytest -q
  ```
  Run specific test file:
  ```bash
  cd api && ../.venv/bin/pytest tests/test_html_sanitizer.py -v
  ```

- **Frontend (Vitest):**
  ```bash
  npm --prefix frontend test -- --run
  ```

- **Frontend Typecheck & Build:**
  ```bash
  npm --prefix frontend run build
  ```

- **Edge functions (Node):**
  ```bash
  node --test infra/tests/*.test.mjs
  ```

## Commit & PR Message Format

Always include agent number, task number, and description:

```
agent{N} task {X.Y}: description
```

Examples:
```
agent1 task 1.11: Wire CloudNS provider, auth vars, echo9.net zone
agent2 task 2.1: Add tenant admin sidebar with Shadcn/UI
agent1 task 1.11, 1.12: CloudNS provider + DNS records for echo9.net
```

## Key Directories & Architecture Docs

| Path | Purpose |
|------|---------|
| `GLOSSARY.md` | Ubiquitous language & deep-module definitions |
| `docs/SPEC.md` | Technical specification for the 5 deep modules & 9 bug fixes |
| `docs/UNATTENDED_ORCHESTRATION.md` | Unattended Opus 4.6 runbook & dependency-graphed tickets (`T-01`–`T-12`) |
| `docs/adr/` | Architectural Decision Records (`ADR-0001`, `ADR-0002`) |
| `api/` | Lambda handler code (Python) |
| `api/templates/` | Template renderers for static site publish |
| `frontend/src/` | React SPA source |
| `infra/` | OpenTofu config + CloudFront Functions + Cloudflare Worker. The Lambda bundle is built by `scripts/build-lambda-package.sh` into `infra/.build/api_lambda/` — run it before `tofu validate/plan` |
| `docs/` | Architecture docs, schema, plans |

## Important Patterns

- **Split Edge Routing**: `app.echo9.net` / `stage.echo9.net` serve the React Admin SPA; `*.echo9.net` and `(www.)echo9.net` serve static HTML directly from `S3-9host-sites` at `/` via `cf-site-content.js` + CloudFront KeyValueStore (`9host-site-hosts-kvs`).
- **Custom Domains (Cloudflare for SaaS)**: Custom hostnames point `CNAME -> proxy.echo9.net`, where a Cloudflare Worker forwards `X-Forwarded-Host` to CloudFront (`cf-site-content.js` + KVS).
- **Single DynamoDB table** (`9host-main` behind `TenantStore`): pk/sk with GSIs (`byUser`, `byDomain`, `bySiteSlug`, `byEntity`).
- **Hybrid Auth (`RequestContext`)**: Cognito User Pool (`USER#{sub}`) for Tenant Admins & Superadmins + DynamoDB `TUSER` / `ROLE` / `GROUP` entities for tenant-managed collaborators.
- **Static HTML publish (`SiteCompiler` + `SiteStoragePort`)**: Pure `compile_site(snapshot, mode)` with HTML sanitization and root-relative links (`/`), uploaded to S3 `published/v{N}/` + `published/current/` and synced to CloudFront KVS.
- **Feature-Flagged Billing**: Controlled by `VITE_ENABLE_BILLING` (default `false` in MVP).
