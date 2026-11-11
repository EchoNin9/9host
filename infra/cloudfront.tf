# ------------------------------------------------------------------------------
# CloudFront distributions (T-08 edge split, docs/SPEC.md §3 Module 1A):
#   Admin SPA ("frontend"):  staging    -> stage.{domain}
#                            production -> app.{domain} (+ prod.{domain} for cutover)
#   Public Sites & Landing:  sites      -> *.{domain}, {landing}, www.{landing}
# S3 origins with OAC. ACM certs (us-east-1). Admin SPA routing via cf-spa-routing.js.
# The Admin SPA calls API Gateway directly (VITE_API_URL), so there is no /api/* behavior.
# ------------------------------------------------------------------------------

# Origin Access Control — CloudFront accesses S3 via SigV4 (no public bucket)
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "9host-frontend-oac"
  description                       = "OAC for 9host frontend S3 buckets"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ------------------------------------------------------------------------------
# Staging: stage.echo9.net
# ------------------------------------------------------------------------------
resource "aws_cloudfront_distribution" "staging" {
  provider = aws.us_east_1

  enabled             = true
  is_ipv6_enabled     = true
  comment             = "9host staging frontend"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  wait_for_deployment = false

  aliases = [for d in var.domains : "stage.${d}"]

  origin {
    domain_name              = aws_s3_bucket.frontend_staging.bucket_regional_domain_name
    origin_id                = "S3-9host-frontend-staging"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # Task 8.1: Media origin for staging — display uploaded media in admin UI
  origin {
    domain_name              = aws_s3_bucket.media.bucket_regional_domain_name
    origin_id                = "S3-9host-media-staging"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # Task 8.1: Media — /media/{tenant}/{site}/{filename} → 9host-media (staging)
  ordered_cache_behavior {
    path_pattern           = "/media/*"
    target_origin_id       = "S3-9host-media-staging"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.media_content.arn
    }

    min_ttl     = 0
    default_ttl = 86400
    max_ttl     = 31536000
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-9host-frontend-staging"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    # SPA routing: CF Function rewrites non-file paths to /index.html
    # (replaces custom_error_response so /media/* returns real S3 errors)
    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_routing.arn
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.main.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  tags = {
    Name = "9host-frontend-staging"
  }
}

# S3 bucket policy: allow CloudFront OAC (staging) to read staging bucket.
# T-08: the sites distribution no longer serves the Admin SPA, so its grant is removed.
resource "aws_s3_bucket_policy" "frontend_staging" {
  bucket = aws_s3_bucket.frontend_staging.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontStaging"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.frontend_staging.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.staging.arn
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.frontend_staging]
}

# ------------------------------------------------------------------------------
# Production Admin SPA: app.echo9.net (+ prod.echo9.net kept for cutover compat)
# ------------------------------------------------------------------------------
resource "aws_cloudfront_distribution" "production" {
  provider = aws.us_east_1

  enabled             = true
  is_ipv6_enabled     = true
  comment             = "9host production frontend"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  wait_for_deployment = false

  aliases = flatten([for d in var.domains : ["app.${d}", "prod.${d}"]])

  origin {
    domain_name              = aws_s3_bucket.frontend_production.bucket_regional_domain_name
    origin_id                = "S3-9host-frontend-production"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-9host-frontend-production"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    # SPA routing: CF Function rewrites non-file paths to /index.html
    # (replaces custom_error_response so /media/* returns real S3 errors)
    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa_routing.arn
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.main.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  tags = {
    Name = "9host-frontend-production"
  }
}

resource "aws_s3_bucket_policy" "frontend_production" {
  bucket = aws_s3_bucket.frontend_production.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontProduction"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.frontend_production.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.production.arn
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.frontend_production]
}

# ------------------------------------------------------------------------------
# T-06: HostMappingKVS — hostname -> {"tenant","site_id"} (docs/SPEC.md §1B)
# Host keys are written by the 9host-api Lambda (api/site_storage.py) on publish
# and on custom-domain activation. "__preview_jwt_secret__" holds the draft
# preview HS256 key (same value as the 9host-jwt-signing-key secret).
# ------------------------------------------------------------------------------
resource "aws_cloudfront_key_value_store" "site_hosts" {
  name    = "9host-site-hosts-kvs"
  comment = "9host HostMappingKVS: hostname -> {tenant, site_id}; preview JWT secret"
}

resource "aws_cloudfrontkeyvaluestore_key" "preview_jwt_secret" {
  key_value_store_arn = aws_cloudfront_key_value_store.site_hosts.arn
  key                 = "__preview_jwt_secret__"
  value               = random_password.jwt_signing.result
}

# T-08: Landing page (US-02) — (www.)echo9.net -> landing site. Only when var.landing_site is set.
resource "aws_cloudfrontkeyvaluestore_key" "landing" {
  for_each = var.landing_site == null ? toset([]) : toset([var.landing_domain, "www.${var.landing_domain}"])

  key_value_store_arn = aws_cloudfront_key_value_store.site_hosts.arn
  key                 = each.value
  value               = jsonencode({ tenant = var.landing_site.tenant, site_id = var.landing_site.site_id })
}

# ------------------------------------------------------------------------------
# Task 1.97 / T-06: CloudFront Function — Host/X-Forwarded-Host → KVS → S3 path rewrite
# ------------------------------------------------------------------------------
resource "aws_cloudfront_function" "site_content" {
  name    = "9host-site-content"
  runtime = "cloudfront-js-2.0"
  comment = "Site content: Host via 9host-site-hosts-kvs (or /site/{tenant}/{site_id}/*) → S3"
  publish = true

  key_value_store_associations = [aws_cloudfront_key_value_store.site_hosts.arn]

  code = file("${path.module}/cf-site-content.js")
}

# ------------------------------------------------------------------------------
# Task 1.118: CloudFront Function — /preview?token=jwt → draft S3 path
# ------------------------------------------------------------------------------
resource "aws_cloudfront_function" "preview_content" {
  name    = "9host-preview-content"
  runtime = "cloudfront-js-2.0"
  comment = "Draft preview: /preview?token=jwt (HS256 verified via KVS secret) → S3 draft/ path"
  publish = true

  key_value_store_associations = [aws_cloudfront_key_value_store.site_hosts.arn]

  code = file("${path.module}/cf-preview-content.js")
}

# ------------------------------------------------------------------------------
# Task 1.110: CloudFront Function — /media/{tenant}/{site}/{filename} → S3
# ------------------------------------------------------------------------------
resource "aws_cloudfront_function" "media_content" {
  name    = "9host-media-content"
  runtime = "cloudfront-js-2.0"
  comment = "Media path rewrite: /media/{tenant}/{site}/{filename} → S3"
  publish = true

  code = file("${path.module}/cf-media-content.js")
}

# ------------------------------------------------------------------------------
# SPA routing for default behavior — replaces distribution-level custom_error_response
# so /site/* and /media/* behaviors can return real S3 errors instead of the SPA.
# ------------------------------------------------------------------------------
resource "aws_cloudfront_function" "spa_routing" {
  name    = "9host-spa-routing"
  runtime = "cloudfront-js-2.0"
  comment = "SPA routing: non-file paths → /index.html (admin frontend)"
  publish = true

  code = file("${path.module}/cf-spa-routing.js")
}

# ------------------------------------------------------------------------------
# Task 1.78 / T-08: Public Sites & Landing distribution (*.echo9.net, echo9.net, www)
# Default behavior serves published static HTML from 9host-sites via cf-site-content.js
# (Host / X-Forwarded-Host -> 9host-site-hosts-kvs -> /{tenant}/{site_id}/published/current/...).
# Host is NOT forwarded to S3 (forwarded_values has no headers); the viewer-request
# function sees every viewer header (incl. X-Forwarded-Host) without a cache-key change,
# and the cache key is the rewritten, per-site URI.
# ------------------------------------------------------------------------------
resource "aws_cloudfront_distribution" "sites" {
  provider = aws.us_east_1

  enabled             = true
  is_ipv6_enabled     = true
  comment             = "9host public sites + landing (*.echo9.net, echo9.net)"
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  wait_for_deployment = false

  # Landing aliases are gated: echo9.net/www.echo9.net are currently attached to an
  # unmanaged distribution (E164B9WJ8ALT9F) — adding them before it releases them fails
  # the whole update with CNAMEAlreadyExists. Flip var.serve_landing_domain after cutover.
  aliases = concat(
    [for d in var.domains : "*.${d}"],
    var.serve_landing_domain ? [var.landing_domain, "www.${var.landing_domain}"] : []
  )

  # Task 1.97: 9host-sites origin for published site content
  origin {
    domain_name              = aws_s3_bucket.sites.bucket_regional_domain_name
    origin_id                = "S3-9host-sites"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # Task 1.110: 9host-media origin for tenant uploads
  origin {
    domain_name              = aws_s3_bucket.media.bucket_regional_domain_name
    origin_id                = "S3-9host-media"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # Task 1.110: Media — /media/{tenant}/{site}/{filename} → 9host-media
  ordered_cache_behavior {
    path_pattern           = "/media/*"
    target_origin_id       = "S3-9host-media"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.media_content.arn
    }

    min_ttl     = 0
    default_ttl = 86400
    max_ttl     = 31536000
  }

  # Task 1.118: Draft preview — /preview*?token=jwt → 9host-sites draft/
  ordered_cache_behavior {
    path_pattern           = "/preview*"
    target_origin_id       = "S3-9host-sites"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = true
      cookies {
        forward = "none"
      }
    }

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.preview_content.arn
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  # Task 1.97: Legacy site content — /site/{tenant}/{site_id}/* → 9host-sites
  ordered_cache_behavior {
    path_pattern           = "/site/*"
    target_origin_id       = "S3-9host-sites"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.site_content.arn
    }

    min_ttl     = 0
    default_ttl = 60
    max_ttl     = 300
  }

  # T-08 (US-01/US-02): Host-routed published site — /* → 9host-sites published/current/
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-9host-sites"
    compress               = true
    viewer_protocol_policy = "redirect-to-https"

    # No headers forwarded: Host stays the S3 origin host (required for OAC/S3).
    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.site_content.arn
    }

    # published/current/ is overwritten in place on publish — keep TTLs short.
    min_ttl     = 0
    default_ttl = 60
    max_ttl     = 300
  }

  # No custom_error_response: missing pages return real S3 403/404 errors.

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
    Name = "9host-frontend-sites"
  }
}

