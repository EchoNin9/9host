# ------------------------------------------------------------------------------
# CloudNS DNS (Task 1.11) — standalone config for echo9.net zone
# Run separately: cd infra/cloudns && tofu init && tofu apply
# Does not block main infra CI. Task 1.12 will add DNS records here.
# ------------------------------------------------------------------------------

terraform {
  required_providers {
    cloudns = {
      source  = "ClouDNS/cloudns"
      version = "~> 1.0"
    }
  }
}

provider "cloudns" {
  auth_id    = var.cloudns_auth_id
  password   = var.cloudns_password
  rate_limit = 10
}

resource "cloudns_dns_zone" "echo9_net" {
  domain = var.domain
  type   = "master"
}
