# ------------------------------------------------------------------------------
# Runbook task F: standalone (www.)echo9.net landing website (owner decision 2026-11-11).
# The landing page is its own static website (repo landing/), NOT a tenant site:
# it is never mapped in 9host-site-hosts-kvs and has no CloudFront Function.
# Keep var.serve_landing_domain = false and var.landing_site = null.
#
# Staging alias: preview.{domain} (a specific alias may coexist with *.{domain} on the
# sites distribution). Production cutover (echo9.net + www.echo9.net) is an owner step:
# see docs/RUNBOOK_POST_CUTOVER.md §3 F.
# Content is synced by CI: aws s3 sync landing/ s3://9host-landing/ --delete
# ------------------------------------------------------------------------------

locals {
  landing_aliases = ["preview.${var.domains[0]}"]

  # AWS managed cache policy "Managed-CachingOptimized" (fixed, account-independent ID).
  # Referenced by ID instead of a data source so CI needs no cloudfront:ListCachePolicies.
  managed_caching_optimized_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
}

resource "aws_s3_bucket" "landing" {
  bucket = "9host-landing"

  tags = {
    Name = "9host-landing"
  }
}

resource "aws_s3_bucket_ownership_controls" "landing" {
  bucket = aws_s3_bucket.landing.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "landing" {
  bucket = aws_s3_bucket.landing.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_distribution" "landing" {
  provider = aws.us_east_1

  enabled             = true
  is_ipv6_enabled     = true
  comment             = "9host-landing"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  wait_for_deployment = false

  aliases = local.landing_aliases

  origin {
    domain_name              = aws_s3_bucket.landing.bucket_regional_domain_name
    origin_id                = "S3-9host-landing"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-9host-landing"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"
    cache_policy_id        = local.managed_caching_optimized_policy_id
  }

  # The OAC grant is s3:GetObject only (no ListBucket), so S3 answers 403 for a
  # missing key. Serve /404.html with a real 404 status for both.
  custom_error_response {
    error_code            = 403
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 60
  }

  custom_error_response {
    error_code            = 404
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 60
  }

  # Existing *.{domain} wildcard cert (also carries the bare echo9.net apex SAN).
  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.wildcard.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  tags = {
    Name = "9host-landing"
  }
}

# Only the 9host-landing distribution may read the bucket (OAC, SigV4).
resource "aws_s3_bucket_policy" "landing" {
  bucket = aws_s3_bucket.landing.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontLanding"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.landing.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.landing.arn
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.landing]
}
