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
- Runtime: `cloudfront-js-2.0` (ES5-like, no ES6+ features, no async/await).
- Must be pure functions — no external calls, no sub-requests.

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

## Key Directories

| Path | Purpose |
|------|---------|
| `api/` | Lambda handler code (Python) |
| `api/templates/` | Template renderers for static site publish |
| `frontend/src/` | React SPA source |
| `infra/` | OpenTofu config + CloudFront Functions |
| `docs/` | Architecture docs, schema, plans |

## Important Patterns

- **Single DynamoDB table** (`9host-main`): pk/sk with GSIs (byUser, byDomain, bySiteSlug)
- **Static HTML publish**: Template + DynamoDB content rendered to HTML, uploaded to S3 `published/current/`
- **Versioned publish**: `published/v{N}/` immutable snapshots, `current.json` atomic pointer
- **Site serving**: CloudFront Function rewrites `/site/{tenant}/{site_id}/*` to S3 keys
- **Draft preview**: JWT-based token, CF Function validates at edge, serves from `draft/` prefix
