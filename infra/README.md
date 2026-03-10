# 9host Infrastructure

Infrastructure as Code uses **OpenTofu** (open-source Terraform fork).

**DNS:** CloudNS.net hosts echo9.net. **prod.echo9.net** & **stage.echo9.net** = 9host app. **www.echo9.net** & **echo9.net** = separate (main site). CloudNS zone managed via `infra/cloudns/` (see docs/CLOUDNS.md).

## Prerequisites

- AWS CLI configured (`aws configure` or `AWS_PROFILE`)
- OpenTofu installed (`brew install opentofu`)

## Phase 1: IAM roles + SSL certificates

1. **Create `infra/terraform.tfvars`** (or pass `-var`):
   ```hcl
   github_org_repo = "EchoNin9/9host"
   domains         = ["echo9.net", "echo9.ca"]
   ```

2. **Apply** (run locally with `AWS_PROFILE=echo9` or equivalent):
   ```bash
   cd infra
   tofu init
   tofu plan -var="github_org_repo=EchoNin9/9host" -var='domains=["echo9.net","echo9.ca"]'
   tofu apply -var="github_org_repo=EchoNin9/9host" -var='domains=["echo9.net","echo9.ca"]'
   ```

3. **Add GitHub repo variables** (Settings → Secrets and variables → Actions → Variables):
   - `AWS_ROLE_ARN_STAGING` = `tofu output -raw github_var_aws_role_arn_staging`
   - `AWS_ROLE_ARN_PRODUCTION` = `tofu output -raw github_var_aws_role_arn_production`
   - `AWS_REGION` (optional) = `us-east-1`

4. **Add ACM validation records to CloudNS:** Run `tofu output acm_validation_records` and add each CNAME to your echo9.net zone in CloudNS.

5. **STOP.** Wait for ACM certificate to show "Issued" (5–30 min typically). See TASKS.md Save Point.

6. **Resume** when cert is Issued — continue with CloudFront/CI-CD.

## OIDC provider already exists?

If you get `EntityAlreadyExists` for the GitHub OIDC provider, import it:

```bash
tofu import aws_iam_openid_connect_provider.github arn:aws:iam::YOUR_ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com
```
