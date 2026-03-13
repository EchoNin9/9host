# Concurrent Batch Jobs — agent1 & agent2

> **Purpose:** Task batches that agent1 and agent2 can run in parallel without file conflicts or API dependencies.  
> **Reference:** [TASKS.md](../TASKS.md) | [ORCHESTRATION.md](ORCHESTRATION.md)

---

## Current Batches (Plan Evaluation Roadmap 1.76–1.81, 2.77–2.82)

Optimized for **maximum concurrent agent work**: agent1 and agent2 run in parallel within each batch where dependencies allow.

### Batch 1 — **agent1 + agent2 concurrent**

| Agent | Tasks | Notes |
|-------|-------|-------|
| **agent1** | 1.76 | bySiteSlug GSI (infra/dynamodb.tf, dynamodb_helpers) |
| **agent2** | 2.75, 2.78, 2.82 | FIX /login/site 503 handling; Echo9 Branding; Tier-Specific Locked States |

**Why safe:** No shared files. agent1: `infra/`, `api/`, `docs/`. agent2: `frontend/`. All tasks independent.

---

### Batch 2 — agent1 only (unblocks 2.77)

| Agent | Tasks | Notes |
|-------|-------|-------|
| **agent1** | 1.77 | Enforce Global Slug + GET /api/validate-slug (sites_handler, handler) |

**Why sequential:** 2.77 (slug check UI) needs validate-slug endpoint. No agent2 work this batch.

---

### Batch 3 — **agent1 + agent2 concurrent**

| Agent | Tasks | Notes |
|-------|-------|-------|
| **agent1** | 1.79 | Site Preview API |
| **agent2** | 2.77 | Real-time Slug Check (uses validate-slug from 1.77) |

**Why safe:** Different domains. 2.77 depends on 1.77 ✅ (batch 2).

---

### Batch 4 — **agent1 + agent2 concurrent**

| Agent | Tasks | Notes |
|-------|-------|-------|
| **agent1** | 1.80, 1.81 | Self-Serve Modules tier validation; DNS Verification |
| **agent2** | 2.78, 2.79, 2.82 | Branding; Module Marketplace; Locked States (if not done in Batch 1) |

**Why safe:** agent1: PATCH /api/tenant, domains_handler, DOMAIN schema. agent2: frontend only. No cross-deps.

---

### Batch 5 — **agent1 + agent2 concurrent**

| Agent | Tasks | Notes |
|-------|-------|-------|
| **agent1** | 1.78 | Wildcard Site Routing (*.echo9.net) |
| **agent2** | 2.80, 2.81 | Site Previewer (← 1.79); Domain Setup Guide (← 1.81) |

**Why safe:** 2.80 depends on 1.79 ✅ (batch 3). 2.81 depends on 1.81 ✅ (batch 4). agent1: ACM, CloudFront, middleware.

---

### Batch 6 — agent4 (future)

| Agent | Tasks | Notes |
|-------|-------|-------|
| **agent4** | 4.1 | Self-serve tenant signup flow |

---

## Quick reference

| Batch | agent1 | agent2 | Concurrency |
|-------|--------|--------|-------------|
| **1** | 1.76 | 2.75, 2.78, 2.82 | ✅ agent1 + agent2 |
| **2** | 1.77 | — | agent1 only |
| **3** | 1.79 | 2.77 | ✅ agent1 + agent2 |
| **4** | 1.80, 1.81 | 2.78, 2.79, 2.82 | ✅ agent1 + agent2 |
| **5** | 1.78 | 2.80, 2.81 | ✅ agent1 + agent2 |
| **6** | — | — | agent4: 4.1 |

---

## Historical (Complete)

### Batch 1 — ~~Run concurrently~~ ✅ Complete
- agent1: 1.25, 1.26, 1.27 | agent2: 2.16

### Batch 2 — ~~agent2 only~~ ✅ Complete
- agent2: 2.14, 2.15, 2.17

### Batch 3 — ~~agent1~~ ✅ Complete
- agent1: 1.28–1.33 (tenant modules + templates)
