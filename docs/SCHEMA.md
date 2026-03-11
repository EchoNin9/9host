# 9host DynamoDB Single-Table Schema

> **Table:** `9host-main`  
> **Rule:** Every item MUST have a Partition Key starting with `TENANT#`.  
> **Reference:** Orangewhip used `USER#{sub}` + `PROFILE`; 9host extends with tenant prefix.

---

## Design Principles

1. **Tenant isolation:** All PKs start with `TENANT#{slug}`. No cross-tenant queries without explicit admin bypass.
2. **Single-table:** All entity types live in one table. Entity type is encoded in PK/SK.
3. **Subdomain routing:** `tenant_slug` comes from URL (e.g. `acme.echo9.net` → `acme`).

---

## Entity Layout

### Base Table: PK + SK

| Entity        | PK              | SK                    | Description                    |
|---------------|------------------|------------------------|--------------------------------|
| Tenant        | `TENANT#{slug}`  | `TENANT`               | Tenant metadata, tier, billing |
| User Profile  | `TENANT#{slug}`  | `USER#{sub}#PROFILE`   | User profile within tenant     |
| Site          | `TENANT#{slug}`  | `SITE#{id}`            | Hosted website                 |
| Custom Domain | `TENANT#{slug}`  | `DOMAIN#{domain}`      | Domain → site mapping (Pro+)   |
| User Permissions | `TENANT#{slug}`  | `USER#{sub}#PERMISSIONS` | Per-user module access (Task 1.25) |
| Site Template | `TENANT#_platform` | `TEMPLATE#{slug}`   | Platform site templates (Task 1.30) |

**Slug rules:** Lowercase, alphanumeric + hyphen. Example: `acme-corp`, `my-band`.

---

## Entity Attributes

### Tenant

```
PK: TENANT#acme
SK: TENANT
---
name: string           # Display name
tier: string           # FREE | PRO | BUSINESS
owner_sub: string      # Cognito sub of primary tenantadmin (Task 1.26)
module_overrides: map  # (optional) Task 1.28. Override tier features: { custom_domains: true, advanced_analytics: true }
stripe_customer_id: S   # (optional) For agent3
created_at: string     # ISO8601
updated_at: string
```

### User Profile

```
PK: TENANT#acme
SK: USER#abc123-cognito-sub#PROFILE
---
sub: string            # Cognito sub (denormalized for GSI)
email: string
name: string
role: string           # admin | manager | editor | member
created_at: string
updated_at: string
```

### Site

```
PK: TENANT#acme
SK: SITE#site-uuid
---
name: string
slug: string           # URL path segment, e.g. "my-site"
status: string         # draft | published
template_id: string    # (optional) Task 1.32. Template slug used to create site.
created_at: string
updated_at: string
```

### Site Template (Task 1.30–1.33)

Platform-level templates. Stored under `TENANT#_platform` to satisfy PK rule.

```
PK: TENANT#_platform
SK: TEMPLATE#musician-band
---
slug: string           # musician-band | personal-tech | personal-resume | professional-services | business-generic
name: string           # Display name
description: string    # Short description
tier_required: string  # FREE | PRO | BUSINESS — minimum tier to use this template
components: map        # JSON structure: which backend components/pages to include
created_at: string
updated_at: string
```

**Templates:** musician-band, personal-tech, personal-resume, professional-services, business-generic

**Access:** GET /api/templates returns tenant-tier-filtered list. Superadmin CRUD via /api/admin/templates.

### Custom Domain (Pro+)

```
PK: TENANT#acme
SK: DOMAIN#example.com
---
site_id: string        # SITE#id
status: string         # pending | verified
created_at: string
updated_at: string
```

### User Permissions (Task 1.25)

```
PK: TENANT#acme
SK: USER#{sub}#PERMISSIONS
---
permissions: map       # { sites: bool, domains: bool, analytics: bool, settings: bool }
updated_at: string
```

Tenantadmin configures what tenantuser can access. If missing, all modules allowed (role-based).

---

## Access Patterns

| Pattern                         | Operation | Key Condition                          |
|---------------------------------|-----------|----------------------------------------|
| Get tenant                      | GetItem   | PK=`TENANT#{slug}`, SK=`TENANT`        |
| Get user profile in tenant      | GetItem   | PK=`TENANT#{slug}`, SK=`USER#{sub}#PROFILE` |
| Get site in tenant              | GetItem   | PK=`TENANT#{slug}`, SK=`SITE#{id}`     |
| List users in tenant            | Query     | PK=`TENANT#{slug}`, SK begins_with `USER#` |
| List sites in tenant            | Query     | PK=`TENANT#{slug}`, SK begins_with `SITE#` |
| List domains in tenant          | Query     | PK=`TENANT#{slug}`, SK begins_with `DOMAIN#` |
| List tenants for user (by sub)  | Query GSI | GSI1PK=`USER#{sub}`, SK begins_with `TENANT#` |
| Get user permissions            | GetItem   | PK=`TENANT#{slug}`, SK=`USER#{sub}#PERMISSIONS` |
| List templates (platform)       | Query     | PK=`TENANT#_platform`, SK begins_with `TEMPLATE#` |

---

## GSIs

### GSI1: byUser (user → tenants)

**Purpose:** "Which tenants does this Cognito user belong to?" (tenant switcher, auth checks)

| Attribute | Key Type | Example                |
|-----------|----------|------------------------|
| gsi1pk    | Partition| `USER#{sub}`           |
| gsi1sk    | Sort     | `TENANT#{slug}#PROFILE`|

**Projection:** ALL

**Query:** `gsi1pk = USER#{sub}` → returns all tenant memberships for user.

### GSI2: byDomain (domain → tenant/site)

**Purpose:** "Which tenant/site does `example.com` map to?" (routing, SSL)

| Attribute | Key Type | Example           |
|-----------|----------|-------------------|
| gsi2pk    | Partition| `DOMAIN#{domain}` |
| gsi2sk    | Sort     | `TENANT#{slug}`   |

**Projection:** ALL

**Query:** `gsi2pk = DOMAIN#example.com` → returns tenant + site for custom domain.

---

## Migration from Orangewhip

| Orangewhip (single-tenant) | 9host (multi-tenant)                    |
|----------------------------|----------------------------------------|
| `USER#{sub}`               | `TENANT#{slug}` (partition for all)    |
| `PROFILE`                  | `USER#{sub}#PROFILE` (SK)              |
| Single band                | Multiple tenants via slug              |
| Cognito groups             | Cognito + tenant membership (role)     |

---

## Lambda Context

Middleware extracts `tenant_slug` from:

- Subdomain: `{tenant}.echo9.net` → `tenant`
- Header: `X-Tenant-Slug` (for API calls)
- Path: `/{tenant}/...` (fallback)

Injected into Lambda event: `event.tenant_slug`.
