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

- [ ] Published Site Viewing: site-slug resolution, CF path format (1.107, 1.108) [agent1]
- [ ] Published Site Viewing: RootRoute redirect with tenant_slug (2.98) [agent2]
- [ ] Published Site Viewing: template-aware publish, media origin (1.109–1.111) [agent1]
