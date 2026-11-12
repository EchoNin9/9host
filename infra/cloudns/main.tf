# ------------------------------------------------------------------------------
# CloudNS DNS (Task 1.11, 1.12, 1.14, T-24) — zones only.
# Run: cd infra/cloudns && tofu init && tofu plan -refresh=false
# Credentials from AWS Secrets Manager (9host-cloudns). Never use tfvars for password.
#
# T-24: DNS *records* are NOT managed here. Provider ClouDNS/cloudns 1.0.10 (and 1.3.3)
# cannot read records back (retrec.priority string vs number), so every refresh fails.
#   - Edge records (app, sites-origin, tools, preview on echo9.net) are upserted by
#     scripts/edge_records.py (dry-run by default; --apply to write).
#   - Legacy records (stage, *, ACM validation CNAMEs) are live and managed manually.
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

# Read main infra outputs (domains list, secret ARN)
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
  domains = length(var.domains) > 0 ? var.domains : data.terraform_remote_state.infra.outputs.domains
}

# DNS zone per domain (echo9.net)
resource "cloudns_dns_zone" "zone" {
  for_each = toset(local.domains)
  domain   = each.value
  type     = "master"
}
