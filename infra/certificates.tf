# ------------------------------------------------------------------------------
# Phase 1: SSL certificates (Task 1.13, 1.78)
# ACM cert for stage/prod across all domains (echo9.net, echo9.ca). DNS via CloudNS.
# Task 1.78: Wildcard cert for *.echo9.net (sites + tenant subdomains).
# Add validation records to CloudNS — see outputs.
# ------------------------------------------------------------------------------

locals {
  # All Admin SPA hostnames: stage.* and app.* per domain
  acm_domains = flatten([
    for d in var.domains : ["stage.${d}", "app.${d}"]
  ])
  # Task 1.78: Wildcard for sites/tenant routing (*.echo9.net, *.echo9.ca)
  # T-08: + bare landing apex (echo9.net). www.echo9.net is covered by *.echo9.net.
  # ACM reuses the *.echo9.net DNS validation CNAME for the apex.
  acm_wildcard_domains = concat([for d in var.domains : "*.${d}"], [var.landing_domain])
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

# T-08: Block CloudFront updates until the (possibly replaced) certs are ISSUED, so a
# SAN change never attaches a PENDING_VALIDATION cert (InvalidViewerCertificate).
# No-op for certs that are already issued.
resource "aws_acm_certificate_validation" "main" {
  provider        = aws.us_east_1
  certificate_arn = aws_acm_certificate.main.arn
}

resource "aws_acm_certificate_validation" "wildcard" {
  provider        = aws.us_east_1
  certificate_arn = aws_acm_certificate.wildcard.arn
}

# NOTE: Add the validation CNAME records (see outputs) to CloudNS.
# OpenTofu apply completes immediately. Certs validate once DNS propagates in CloudNS.
