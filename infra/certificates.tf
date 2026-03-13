# ------------------------------------------------------------------------------
# Phase 1: SSL certificates (Task 1.13, 1.78)
# ACM cert for stage/prod across all domains (echo9.net, echo9.ca). DNS via CloudNS.
# Task 1.78: Wildcard cert for *.echo9.net (sites + tenant subdomains).
# Add validation records to CloudNS — see outputs.
# ------------------------------------------------------------------------------

locals {
  # All hostnames: stage.echo9.net, prod.echo9.net, stage.echo9.ca, prod.echo9.ca
  acm_domains = flatten([
    for d in var.domains : ["stage.${d}", "prod.${d}"]
  ])
  # Task 1.78: Wildcard for sites/tenant routing (*.echo9.net, *.echo9.ca)
  acm_wildcard_domains = [for d in var.domains : "*.${d}"]
}

# ACM certificate — all stage/prod hostnames (CloudFront requires us-east-1)
resource "aws_acm_certificate" "main" {
  provider          = aws.us_east_1
  domain_name       = local.acm_domains[0]
  validation_method = "DNS"

  subject_alternative_names = slice(local.acm_domains, 1, length(local.acm_domains))

  lifecycle {
    create_before_destroy = true
  }
}

# Task 1.78: Wildcard ACM cert for *.echo9.net (sites + tenant subdomains)
resource "aws_acm_certificate" "wildcard" {
  provider          = aws.us_east_1
  domain_name       = local.acm_wildcard_domains[0]
  validation_method = "DNS"

  subject_alternative_names = slice(local.acm_wildcard_domains, 1, length(local.acm_wildcard_domains))

  lifecycle {
    create_before_destroy = true
  }
}

# NOTE: Add the validation CNAME records (see outputs) to CloudNS.
# OpenTofu apply completes immediately. Certs validate once DNS propagates in CloudNS.
