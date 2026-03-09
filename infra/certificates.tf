# ------------------------------------------------------------------------------
# Phase 1: SSL certificates (STOP HERE — see TASKS.md Save Point)
# ACM cert + Route 53 DNS validation records. DNS propagation can take minutes to hours.
# Do not proceed to CloudFront/other infra until cert status is "Issued".
# ------------------------------------------------------------------------------

# Route 53 hosted zone (delegate from registrar: update NS records at your domain registrar)
resource "aws_route53_zone" "main" {
  name = var.domain
}

# ACM certificate — echo9.net + *.echo9.net (CloudFront requires us-east-1)
resource "aws_acm_certificate" "main" {
  provider          = aws.us_east_1
  domain_name       = var.domain
  validation_method = "DNS"

  subject_alternative_names = [
    "*.${var.domain}"
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# DNS validation records — add these to Route 53 so ACM can validate
# Propagation typically takes 5–30 minutes (up to 72 hours in rare cases)
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.main.zone_id
}

# NOTE: aws_acm_certificate_validation is intentionally omitted.
# OpenTofu apply completes immediately. Cert validates once DNS propagates.
# Add validation resource when building CloudFront (Phase 2).
