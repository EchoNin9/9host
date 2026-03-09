# ------------------------------------------------------------------------------
# Phase 1: SSL certificates (STOP HERE — see TASKS.md Save Point)
# ACM cert for stage.echo9.net & prod.echo9.net (9host app). DNS via CloudNS.
# www.echo9.net & echo9.net are separate (main site).
# Add validation records to CloudNS manually — see outputs.
# ------------------------------------------------------------------------------

# ACM certificate — stage.echo9.net + prod.echo9.net (CloudFront requires us-east-1)
resource "aws_acm_certificate" "main" {
  provider          = aws.us_east_1
  domain_name       = "stage.${var.domain}"
  validation_method = "DNS"

  subject_alternative_names = [
    "prod.${var.domain}"
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# NOTE: Add the validation CNAME records (see output acm_validation_records) to CloudNS.
# OpenTofu apply completes immediately. Cert validates once DNS propagates in CloudNS.
