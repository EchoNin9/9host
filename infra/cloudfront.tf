# ------------------------------------------------------------------------------
# CloudFront distributions for stage.echo9.net and prod.echo9.net
# S3 origin with OAC. ACM cert (us-east-1). SPA routing (404/403 -> index.html).
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
  is_ipv6_enabled      = true
  comment              = "9host staging frontend"
  default_root_object  = "index.html"
  price_class         = "PriceClass_100"
  wait_for_deployment = false

  aliases = ["stage.${var.domain}"]

  origin {
    domain_name              = aws_s3_bucket.frontend_staging.bucket_regional_domain_name
    origin_id                = "S3-9host-frontend-staging"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
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

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  # SPA routing: 404/403 -> index.html (React Router)
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.main.arn
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

# S3 bucket policy: allow CloudFront OAC to read staging bucket
resource "aws_s3_bucket_policy" "frontend_staging" {
  bucket = aws_s3_bucket.frontend_staging.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipal"
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
# Production: prod.echo9.net
# ------------------------------------------------------------------------------
resource "aws_cloudfront_distribution" "production" {
  provider = aws.us_east_1

  enabled             = true
  is_ipv6_enabled      = true
  comment              = "9host production frontend"
  default_root_object  = "index.html"
  price_class         = "PriceClass_100"
  wait_for_deployment = false

  aliases = ["prod.${var.domain}"]

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

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.main.arn
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
        Sid    = "AllowCloudFrontServicePrincipal"
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
