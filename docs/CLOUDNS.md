# CloudNS DNS (Task 1.11, 1.12)

9host uses ClouDNS for DNS management of echo9.net. The ClouDNS config (`infra/cloudns/`) manages the zone and DNS records. It reads ACM/CloudFront data from the main infra remote state.

## Prerequisites

- ClouDNS account with API access (Premium DNS, DDoS Protected DNS, or GeoDNS plan)
- API credentials from **Account Settings → API** (auth-id and auth-password)
- AWS credentials (to read main infra remote state)
- Main infra applied at least once (`cd infra && tofu apply`)

## Setup

1. Create an API user in ClouDNS (Account Settings → API)
2. Copy `infra/cloudns/terraform.tfvars.example` to `infra/cloudns/terraform.tfvars`
3. Fill in `cloudns_auth_id` and `cloudns_password`

## Apply

```bash
cd infra/cloudns
tofu init
AWS_PROFILE=echo9 tofu apply -var-file=terraform.tfvars
```

Or pass vars directly:

```bash
tofu apply -var="cloudns_auth_id=12345" -var="cloudns_password=your-password" -var="domain=echo9.net"
```

## DNS records (Task 1.12)

The config creates:

- **ACM validation CNAMEs** — for stage.echo9.net and prod.echo9.net (cert validation)
- **stage.echo9.net** → CloudFront staging distribution
- **prod.echo9.net** → CloudFront production distribution

Values are read from the main infra remote state. Run main infra apply first.

## Zone already exists

If echo9.net was created manually in CloudNS, import it before adding records:

```bash
cd infra/cloudns
tofu import cloudns_dns_zone.echo9_net echo9.net
```

(Check provider docs for the correct import ID format.)

## Resources

- [ClouDNS Terraform provider](https://registry.terraform.io/providers/ClouDNS/cloudns/latest)
- [ClouDNS API docs](https://www.cloudns.net/wiki/article/41/)
