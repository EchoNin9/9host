# OpenTofu Remote State

State is stored in S3 with DynamoDB locking. Use `AWS_PROFILE=echo9` for all aws-cli and tofu commands.

## Bootstrap (one-time)

Run once to create the state bucket and lock table:

```bash
cd infra/bootstrap
AWS_PROFILE=echo9 tofu init
AWS_PROFILE=echo9 tofu apply -auto-approve
```

## Local init

After bootstrap, initialize the main infra with the remote backend:

```bash
AWS_PROFILE=echo9 ./scripts/init-backend.sh
```

If migrating from local state, the script will prompt for migration; it pipes `yes` automatically.

## CI/CD

Workflows use `tofu init -reconfigure -backend-config=...` with bucket/table derived from the OIDC role's account ID. No extra config needed.

## Backend config

- **Bucket:** `9host-tofu-state-{account_id}`
- **Key:** `9host/terraform.tfstate`
- **Lock table:** `9host-tofu-state-lock`

Generated `infra/backend-config.hcl` is gitignored.
