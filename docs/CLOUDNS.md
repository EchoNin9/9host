# CloudNS DNS (Task 1.11, 1.12)

9host uses ClouDNS for DNS management of echo9.net. Credentials are stored in **AWS Secrets Manager** — never in tfvars or env files.

## Prerequisites

- ClouDNS account with API access (Premium DNS, DDoS Protected DNS, or GeoDNS plan)
- API credentials from **Account Settings → API** (auth-id and auth-password)
- AWS credentials (to read main infra remote state and Secrets Manager)
- Main infra applied at least once (`cd infra && tofu apply`)

## Setup

1. **Apply main infra** (creates the `9host-cloudns` secret):
   ```bash
   cd infra && tofu apply
   ```

2. **Store CloudNS credentials in Secrets Manager**:
   ```bash
   aws secretsmanager put-secret-value \
     --secret-id 9host-cloudns \
     --secret-string '{"auth_id":12345,"password":"your-auth-password"}'
   ```

3. **Apply CloudNS config**:
   ```bash
   cd infra/cloudns
   tofu init
   tofu apply -var-file=terraform.tfvars
   ```

The `terraform.tfvars` file should contain only non-sensitive values (e.g. `domain`). Never put credentials in tfvars.

**Migration:** If you have `terraform.tfvars` with `cloudns_auth_id` or `cloudns_password`, remove those lines (credentials are now in Secrets Manager only).

## DNS records (Task 1.12)

The config creates:

- **ACM validation CNAMEs** — for stage.echo9.net and prod.echo9.net (cert validation)
- **stage.echo9.net** → CloudFront staging distribution
- **prod.echo9.net** → CloudFront production distribution

Values are read from the main infra remote state. Run main infra apply first.

## Zone or records already exist

**Zone:** If you get `Error: echo9.net has been already added`:
```bash
cd infra/cloudns
tofu import cloudns_dns_zone.echo9_net echo9.net
```

**Records:** If you get `Error: There is another record for the same host`, the records exist. Either:

1. **Skip record management** (records stay as-is, zone only):
   ```bash
   tofu apply -var="manage_records=false"
   ```

2. **Import records** (if the provider supports it; some versions have a priority-field bug):
```bash
# List record IDs (run from repo root)
AWS_PROFILE=echo9 AWS_REGION=us-east-1 ./infra/cloudns/scripts/import-existing-records.sh

# Then run the import commands it outputs, e.g.:
cd infra/cloudns
tofu import cloudns_dns_record.stage echo9.net/RECORD_ID
tofu import cloudns_dns_record.prod echo9.net/RECORD_ID
tofu import 'cloudns_dns_record.acm_validation["stage.echo9.net"]' echo9.net/RECORD_ID
tofu import 'cloudns_dns_record.acm_validation["prod.echo9.net"]' echo9.net/RECORD_ID
```

Or get record IDs from CloudNS dashboard (Zone → Records → click a record for its ID).

## Resources

- [ClouDNS Terraform provider](https://registry.terraform.io/providers/ClouDNS/cloudns/latest)
- [ClouDNS API docs](https://www.cloudns.net/wiki/article/41/)
