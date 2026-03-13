# ------------------------------------------------------------------------------
# CloudNS DNS (Task 1.11, 1.12, 1.14) — echo9.net + echo9.ca zones + DNS records
# Run: cd infra/cloudns && tofu init && tofu apply -var-file=terraform.tfvars
# Credentials from AWS Secrets Manager (9host-cloudns). Never use tfvars for password.
# ------------------------------------------------------------------------------

terraform {
  required_providers {
    cloudns = {
      source  = "ClouDNS/cloudns"
      version = "~> 1.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

locals {
  cloudns_creds = jsondecode(data.aws_secretsmanager_secret_version.cloudns.secret_string)
}

provider "cloudns" {
  auth_id    = local.cloudns_creds.auth_id
  password   = local.cloudns_creds.password
  rate_limit = 10
}

provider "aws" {
  region = var.aws_region
}

# Read main infra outputs (ACM validation, CloudFront domains, domains list, secret ARN)
data "aws_caller_identity" "current" {}

data "terraform_remote_state" "infra" {
  backend = "s3"
  config = {
    bucket         = "9host-tofu-state-${data.aws_caller_identity.current.account_id}"
    key            = "9host/terraform.tfstate"
    region         = var.aws_region
    dynamodb_table = "9host-tofu-state-lock"
  }
}

data "aws_secretsmanager_secret_version" "cloudns" {
  secret_id = data.terraform_remote_state.infra.outputs.cloudns_secret_arn
}

locals {
  domains         = length(var.domains) > 0 ? var.domains : data.terraform_remote_state.infra.outputs.domains
  acm_records     = data.terraform_remote_state.infra.outputs.acm_validation_records
  acm_wildcard    = data.terraform_remote_state.infra.outputs.acm_wildcard_validation_records
  cf_staging      = data.terraform_remote_state.infra.outputs.cloudfront_staging_domain
  cf_production   = data.terraform_remote_state.infra.outputs.cloudfront_production_domain
  cf_sites        = data.terraform_remote_state.infra.outputs.cloudfront_sites_domain
}

# DNS zone per domain (echo9.net, echo9.ca)
resource "cloudns_dns_zone" "zone" {
  for_each = toset(local.domains)
  domain   = each.value
  type     = "master"
}

# ACM validation CNAMEs (Task 1.12, 1.14)
# ACM name format: _xxx.stage.echo9.net. -> zone echo9.net, record name _xxx.stage
locals {
  acm_by_domain  = var.manage_records ? { for r in local.acm_records : r.domain => r } : {}
  zone_from_fqdn = { for d, r in local.acm_by_domain : d => replace(replace(r.domain, "stage.", ""), "prod.", "") }
}

resource "cloudns_dns_record" "acm_validation" {
  for_each = local.acm_by_domain
  zone     = cloudns_dns_zone.zone[local.zone_from_fqdn[each.key]].domain
  name     = replace(trimsuffix(each.value.name, "."), ".${local.zone_from_fqdn[each.key]}", "")
  type     = "CNAME"
  value    = trimsuffix(each.value.value, ".")
  ttl      = 300
}

# stage.{domain} -> CloudFront staging (per zone)
resource "cloudns_dns_record" "stage" {
  for_each = var.manage_records ? toset(local.domains) : []
  zone     = cloudns_dns_zone.zone[each.key].domain
  name     = "stage"
  type     = "CNAME"
  value    = local.cf_staging
  ttl      = 300
}

# prod.{domain} -> CloudFront production (per zone)
resource "cloudns_dns_record" "prod" {
  for_each = var.manage_records ? toset(local.domains) : []
  zone     = cloudns_dns_zone.zone[each.key].domain
  name     = "prod"
  type     = "CNAME"
  value    = local.cf_production
  ttl      = 300
}

# Task 1.78: *.{domain} -> CloudFront sites (tenant + site subdomains)
resource "cloudns_dns_record" "wildcard" {
  for_each = var.manage_records ? toset(local.domains) : []
  zone     = cloudns_dns_zone.zone[each.key].domain
  name     = "*"
  type     = "CNAME"
  value    = local.cf_sites
  ttl      = 300
}

# Task 1.78: Wildcard ACM validation CNAMEs (*.echo9.net)
locals {
  acm_wildcard_by_domain = var.manage_records ? { for r in local.acm_wildcard : r.domain => r } : {}
  zone_from_wildcard     = { for d, r in local.acm_wildcard_by_domain : d => replace(r.domain, "*.", "") }
}

resource "cloudns_dns_record" "acm_wildcard_validation" {
  for_each = local.acm_wildcard_by_domain
  zone     = cloudns_dns_zone.zone[local.zone_from_wildcard[each.key]].domain
  name     = replace(trimsuffix(each.value.name, "."), ".${local.zone_from_wildcard[each.key]}", "")
  type     = "CNAME"
  value    = trimsuffix(each.value.value, ".")
  ttl      = 300
}
