# 9host Infrastructure

Infrastructure as Code uses **OpenTofu** (open-source Terraform fork).

## Phase 1: SSL certificates (stop here)

1. **Prereqs:** AWS CLI configured, OpenTofu installed (`brew install opentofu`), domain `echo9.net` (or set `domain` variable).

2. **Apply:**
   ```bash
   cd infra
   tofu init
   tofu apply
   ```

3. **Delegate domain:** Add the NS records from `tofu output route53_name_servers` at your domain registrar.

4. **STOP.** Wait for ACM certificate to show "Issued" (5–30 min typically). See TASKS.md Save Point.

5. **Resume** when cert is Issued — continue with CloudFront/CI-CD.
