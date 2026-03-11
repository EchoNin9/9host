# Concurrent Batch Jobs — agent1 & agent2

> **Purpose:** Task batches that agent1 and agent2 can run in parallel without file conflicts or API dependencies.  
> **Reference:** [TASKS.md](../TASKS.md) | [ORCHESTRATION.md](ORCHESTRATION.md)

---

## Batch 1 — ~~Run concurrently~~ ✅ Complete

| Agent | Tasks | Branch | Notes |
|-------|-------|--------|-------|
| **agent1** | 1.25, 1.26, 1.27 | — | Module permissions, owner_sub, tenant users API |
| **agent2** | 2.16 | — | Role-based UI: hide create/edit/delete for tenantuser |

**Why safe:**
- agent1: `api/`, `infra/`, `docs/` — backend only
- agent2: `frontend/` — UI only
- 2.16 depends on 1.24 ✅ (already done)
- No shared files, no API shape changes between them

**agent1 tasks:**
- **1.25** — Add module permissions entity + API (TENANT#slug#USER#sub#PERMISSIONS)
- **1.26** — Add account owner (owner_sub on tenant)
- **1.27** — Add GET /api/tenant/users (list tenant users for tenantadmin)

**agent2 tasks:**
- **2.16** — Role-based UI: hide create/edit/delete for tenantuser in Sites, Domains, Settings

---

## Batch 2 — ~~agent2 only~~ ✅ Complete

| Agent | Tasks | Notes |
|-------|-------|-------|
| **agent2** | 2.14, 2.15, 2.17 | Tenantadmin users, module access, settings owner |

---

## Batch 3 — agent1 (tenant modules + templates)

| Agent | Tasks | Branch | Notes |
|-------|-------|--------|-------|
| **agent1** | 1.28, 1.29, 1.30, 1.31, 1.32, 1.33 | `agent1/task-1.28-1.33` | Modules, tier override, site templates |

**agent1 tasks:**
- **1.28** — Tenant module_overrides + resolved features in GET /api/tenant
- **1.29** — PATCH /api/admin/tenants/{slug} (superadmin: tier, name, module_overrides)
- **1.30** — Site template entity + GET /api/templates (tier-filtered)
- **1.31** — Superadmin templates CRUD: /api/admin/templates
- **1.32** — Add template_id to Site, validate on POST /api/tenant/sites
- **1.33** — Seed templates (musician-band, personal-tech, personal-resume, professional-services, business-generic)

**Docs:** [docs/SCHEMA.md](SCHEMA.md), [docs/TEMPLATES.md](TEMPLATES.md)

---

## Quick reference

| Batch | agent1 | agent2 |
|-------|--------|--------|
| **1** | 1.25, 1.26, 1.27 | 2.16 |
| **2** | — | 2.14, 2.15, 2.17 |
| **3** | 1.28–1.33 | — |
