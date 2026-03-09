# CloudNS DNS (Task 1.11)

9host uses ClouDNS for DNS management of echo9.net. The ClouDNS provider is in a **standalone config** (`infra/cloudns/`) so main infra CI runs without CloudNS credentials.

## Prerequisites

- ClouDNS account with API access (Premium DNS, DDoS Protected DNS, or GeoDNS plan)
- API credentials from **Account Settings → API** (auth-id and auth-password)

## Setup

1. Create an API user in ClouDNS (Account Settings → API)
2. Copy `infra/cloudns/terraform.tfvars.example` to `infra/cloudns/terraform.tfvars`
3. Fill in `cloudns_auth_id` and `cloudns_password`

## Apply

```bash
cd infra/cloudns
tofu init
tofu apply -var-file=terraform.tfvars
```

Or pass vars directly:

```bash
tofu apply -var="cloudns_auth_id=12345" -var="cloudns_password=your-password" -var="domain=echo9.net"
```

## Zone already exists

If echo9.net was created manually in CloudNS, import it:

```bash
cd infra/cloudns
tofu import cloudns_dns_zone.echo9_net echo9.net
```

(Check provider docs for the correct import ID format.)

## Task 1.12

DNS records (ACM validation CNAMEs, stage/prod CNAMEs → CloudFront) will be added to this config in task 1.12.

## Resources

- [ClouDNS Terraform provider](https://registry.terraform.io/providers/ClouDNS/cloudns/latest)
- [ClouDNS API docs](https://www.cloudns.net/wiki/article/41/)
