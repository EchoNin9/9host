# ------------------------------------------------------------------------------
# S3 buckets for frontend static assets (stage/prod)
# CloudFront OAC for access — no public bucket access.
# ------------------------------------------------------------------------------

resource "aws_s3_bucket" "frontend_staging" {
  bucket = "9host-frontend-staging"

  tags = {
    Name = "9host-frontend-staging"
  }
}

# Disable ACLs (AWS best practice) — avoids GetBucketAcl during plan/refresh
resource "aws_s3_bucket_ownership_controls" "frontend_staging" {
  bucket = aws_s3_bucket.frontend_staging.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend_staging" {
  bucket = aws_s3_bucket.frontend_staging.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "frontend_staging" {
  bucket = aws_s3_bucket.frontend_staging.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket" "frontend_production" {
  bucket = "9host-frontend-production"

  tags = {
    Name = "9host-frontend-production"
  }
}

resource "aws_s3_bucket_ownership_controls" "frontend_production" {
  bucket = aws_s3_bucket.frontend_production.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend_production" {
  bucket = aws_s3_bucket.frontend_production.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "frontend_production" {
  bucket = aws_s3_bucket.frontend_production.id

  versioning_configuration {
    status = "Disabled"
  }
}

# ------------------------------------------------------------------------------
# Task 1.90: Sites S3 bucket — published site content
# Key layout: {tenant_slug}/{site_id}/draft/, {tenant_slug}/{site_id}/published/v{N}/, current.json
# OAC for CloudFront (added in 1.97). Versioning for rollback.
# ------------------------------------------------------------------------------
resource "aws_s3_bucket" "sites" {
  bucket = "9host-sites"

  tags = {
    Name = "9host-sites"
  }
}

resource "aws_s3_bucket_ownership_controls" "sites" {
  bucket = aws_s3_bucket.sites.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "sites" {
  bucket = aws_s3_bucket.sites.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "sites" {
  bucket = aws_s3_bucket.sites.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Task 1.97: Allow CloudFront sites distribution to read from 9host-sites
# Custom domain distributions (created dynamically) also need access.
resource "aws_s3_bucket_policy" "sites" {
  bucket = aws_s3_bucket.sites.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontSites"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.sites.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.sites.arn
          }
        }
      },
      {
        Sid    = "AllowCustomDomainDistributions"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.sites.arn}/*"
        Condition = {
          StringLike = {
            "AWS:SourceArn" = "arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/*"
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.sites]
}

# ------------------------------------------------------------------------------
# Task 1.91: Media S3 bucket — tenant uploads (images, files)
# Key layout: {tenant_slug}/{site_id}/{filename}
# ------------------------------------------------------------------------------
resource "aws_s3_bucket" "media" {
  bucket = "9host-media"

  tags = {
    Name = "9host-media"
  }
}

resource "aws_s3_bucket_ownership_controls" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket = aws_s3_bucket.media.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "media" {
  bucket = aws_s3_bucket.media.id

  versioning_configuration {
    status = "Enabled"
  }
}

# CORS for browser uploads: presigned POST from stage/prod frontends
# *.echo9.net covers stage.echo9.net, prod.echo9.net, tenant.stage.echo9.net, etc.
resource "aws_s3_bucket_cors_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  cors_rule {
    allowed_headers   = ["*"]
    allowed_methods   = ["POST", "PUT"]
    allowed_origins   = ["https://*.echo9.net", "https://*.echo9.ca", "http://localhost:5173", "http://localhost:3000"]
    expose_headers    = ["ETag"]
    max_age_seconds   = 3600
  }
}

# Task 1.110: Allow CloudFront sites distribution to read media (for /media/*)
resource "aws_s3_bucket_policy" "media" {
  bucket = aws_s3_bucket.media.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontSites"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.media.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.sites.arn
          }
        }
      },
      {
        Sid    = "AllowCloudFrontStaging"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.media.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.staging.arn
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.media]
}
