# Agent Orchestration Guide

> **Goal:** Enable agent1, agent2, and agent3 to work in parallel (3–4 tasks per session each) without state locks, merge conflicts, or stepping on each other.

---

## 1. Conflict Analysis

### OpenTofu State Lock (Primary Risk)

| Who | Touches State? | When |
|-----|----------------|------|
| **agent1** | Yes (local `tofu apply`) | When testing infra changes |
| **CI (dev.yml)** | Yes | On every push to `develop` |
| **CI (main.yml)** | Yes | On every push to `main` |
| agent2 | No | — |
| agent3 | No* | *Unless agent3 adds infra for webhooks |

**Rule:** Only one tofu operation can hold the DynamoDB lock at a time. agent1 local apply + CI = conflict.

### File Ownership

| Agent | Primary Dirs | Overlap Risk |
|-------|--------------|--------------|
| agent1 | `infra/`, `api/`, `docs/` | — |
| agent2 | `frontend/` | agent3 (checkout UI, tier display) |
| agent3 | `api/` (webhooks), `frontend/` (checkout) | agent2 (frontend), agent1 (api) |

### Shared Files (All Agents)

- `TASKS.md` — status updates (merge conflicts possible)
- `package-lock.json` — if root deps change (rare)

---

## 2. Orchestration Rules

### A. Branch Strategy

```
main (prod)
  └── develop (staging)
        ├── agent1/feature-branch   (infra, API)
        ├── agent2/feature-branch   (frontend)
        └── agent3/feature-branch   (payments)
```

- Each agent works on a **dedicated branch** from `develop`.
- Branch naming: `agent{N}/task-{ids}` (e.g. `agent1/task-1.10-1.13`, `agent2/task-2.2-2.5`).

### B. Tofu State: agent1-Only Rules

1. **agent1 must NOT run `tofu apply` locally** while CI could run (e.g. right after pushing).
2. **agent1 workflow:** Edit infra → `tofu plan` locally (read-only, no lock) → commit → push → CI runs apply.
3. **If agent1 needs to test apply locally:** Run only when no other tofu process is active; avoid pushing until done.
4. **CI concurrency:** Add a concurrency group so only one tofu job runs at a time (see §4).

### C. Merge Order (Reduces Rebase Pain)

Recommended merge sequence when multiple PRs are ready:

1. **agent1 first** — infra + API base (agent3 may depend on API shape).
2. **agent2 second** — frontend (FeatureFlag, tenant UI).
3. **agent3 last** — payments (depends on 2.2 FeatureFlag, may touch api/ and frontend/).

Rebase agent3 onto `develop` after agent1 and agent2 merge.

### D. Session Task Batches (3–4 per Agent)

| Agent | Suggested Batch | Rationale |
|-------|-----------------|-----------|
| **agent1** | 1.10, 1.11, 1.12, 1.13 | API Gateway + CloudNS + DNS; 1.12 depends on 1.11 |
| **agent2** | 2.2, 2.3, 2.5 | FeatureFlag + HOC + tenant migration; 2.3 aligns with 2.2 |
| **agent3** | 3.1, 3.2, 3.3 | Stripe integration + tier mapping + webhooks; sequential |

Alternative agent1 batch: 1.10, 1.11, 1.12 (3 tasks) — defer 1.13/1.14 to next session.

---

## 3. Per-Session Checklist

### Before Starting (Each Agent)

- [ ] Pull latest `develop`: `git checkout develop && git pull`
- [ ] Create branch: `git checkout -b agent{N}/task-{X.Y}-{X.Y}`
- [ ] Read `TASKS.md` for task details and dependencies
- [ ] **agent1 only:** Ensure no CI workflow is currently running tofu (check Actions tab)

### During Work

- [ ] Stay within owned dirs (see §1 File Ownership)
- [ ] **agent1:** Use `tofu plan` for validation; avoid `tofu apply` unless necessary and no CI run
- [ ] Update `TASKS.md` when completing tasks (TODO → DONE)
- [ ] Run `roborev fix` and `roborev refine` before committing

### Before Pushing

- [ ] Rebase on `develop` if others have merged: `git fetch && git rebase origin/develop`
- [ ] Resolve `TASKS.md` conflicts if multiple agents updated (coordinate via comments)
- [ ] **agent1:** If you ran `tofu apply` locally, ensure CI won’t conflict (push during low-activity window)

### After Merge

- [ ] Delete feature branch
- [ ] Update `TASKS.md` on `develop` if not already done

---

## 4. CI Concurrency (Prevent Parallel Tofu)

Add to both `dev.yml` and `main.yml` so only one tofu job runs at a time:

```yaml
jobs:
  deploy:
    concurrency: 9host-tofu-deploy
    runs-on: ubuntu-latest
    # ... rest of job
```

This prevents `dev` and `main` workflows from running tofu apply simultaneously (e.g. if both branches are pushed close together).

---

## 5. Cross-Agent Dependencies

| agent3 Task | Depends On | Owner |
|-------------|------------|-------|
| 3.2 Map Stripe → FeatureFlag tier | 2.2 FeatureFlag utility | agent2 |
| 3.1 Stripe integration | — | agent3 |
| 3.3 Webhooks | 1.10 API Gateway (if webhook is API route) | agent1 |

**Coordination:** agent3 can implement 3.1 and 3.3 in parallel with agent2; 3.2 should wait for 2.2 merge or use a stub/mock tier until FeatureFlag exists.

---

## 6. Quick Reference

| Question | Answer |
|----------|--------|
| Can agent2 and agent3 work at the same time? | Yes, but may conflict on `frontend/` — use separate branches, merge agent2 first. |
| Can agent1 run tofu locally? | Only when CI is idle. Prefer: plan locally, push, let CI apply. |
| How many tasks per session? | 3–4 per agent (see §2.D). |
| Who merges first? | agent1 → agent2 → agent3. |
| TASKS.md conflicts? | Rebase and resolve; keep status updates minimal and append-only where possible. |
