# 9host — Development Status

## Agent Roles

| Agent | Focus | Expertise |
|-------|-------|-----------|
| **agent1** | Backend / Infra | OpenTofu, AWS SAM, DynamoDB Single Table Design, Lambda, Cognito, IAM (all resources prefixed `9host`) |
| **agent2** | Frontend / UI | React, Vite, Tailwind, Shadcn/UI, FeatureGate HOC |
| **agent3** | Payments | Stripe API, subscriptions, webhooks, tier mapping |

## Tech Stack

- **Backend:** AWS Lambda, API Gateway, DynamoDB (single-table design). All AWS resources use prefix `9host`.
- **Auth:** Cognito User Pool
- **Frontend:** React + Vite + TypeScript
- **Styling:** Tailwind CSS + Shadcn/UI

## Active Tasks

See **TASKS.md** for the full task list. Agents should reference it before starting work.

- [ ] Migrate single-user schema to multi-tenant [agent1]
- [ ] Design Tenant Admin Sidebar [agent2]
- [ ] Integrate Roborev post-commit hooks [agent1]
- [ ] FeatureFlag utility + HOC [agent2]
- [ ] Stripe tier subscriptions [agent3]
