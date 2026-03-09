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
