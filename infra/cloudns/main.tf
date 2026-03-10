# ------------------------------------------------------------------------------
# CloudNS DNS (Task 1.11, 1.12) — echo9.net zone + DNS records
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

# Read main infra outputs (ACM validation, CloudFront domains, secret ARN)
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
  acm_records   = data.terraform_remote_state.infra.outputs.acm_validation_records
  cf_staging    = data.terraform_remote_state.infra.outputs.cloudfront_staging_domain
  cf_production = data.terraform_remote_state.infra.outputs.cloudfront_production_domain
}

resource "cloudns_dns_zone" "echo9_net" {
  domain = var.domain
  type   = "master"
}

# ACM validation CNAMEs (Task 1.12)
# ACM name format: _xxx.stage.echo9.net. -> record name _xxx.stage for zone echo9.net
resource "cloudns_dns_record" "acm_validation" {
  for_each = { for i, r in local.acm_records : r.domain => r }
  zone     = cloudns_dns_zone.echo9_net.domain
  name     = replace(trimsuffix(each.value.name, "."), ".${var.domain}", "")
  type     = "CNAME"
  value    = trimsuffix(each.value.value, ".")
  ttl      = 300
}

# stage.echo9.net -> CloudFront staging
resource "cloudns_dns_record" "stage" {
  zone   = cloudns_dns_zone.echo9_net.domain
  name   = "stage"
  type   = "CNAME"
  value  = local.cf_staging
  ttl    = 300
}

# prod.echo9.net -> CloudFront production
resource "cloudns_dns_record" "prod" {
  zone   = cloudns_dns_zone.echo9_net.domain
  name   = "prod"
  type   = "CNAME"
  value  = local.cf_production
  ttl    = 300
}
