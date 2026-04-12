# ------------------------------------------------------------------------------
# Custom domain infrastructure — per-domain CloudFront distributions.
#
# Each custom domain gets its own CloudFront distribution (created dynamically
# by the ACM handler Lambda when the cert is issued). This file defines the
# shared resources: CF function for path resolution and the OAC ID output.
#
# The Lambda uses these to create distributions with:
#   - Origin: 9host-sites S3 bucket, path /{tenant}/{site_id}/published/current
#   - CF function association for path resolution + www→apex redirect
#   - Per-domain ACM cert + aliases (domain.com, www.domain.com)
# ------------------------------------------------------------------------------

resource "aws_cloudfront_function" "custom_domain" {
  name    = "9host-custom-domain"
  runtime = "cloudfront-js-2.0"
  comment = "Custom domain: path resolution + www→apex redirect"
  publish = true

  code = file("${path.module}/cf-custom-domain.js")
}
