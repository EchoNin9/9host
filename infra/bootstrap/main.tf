# Bootstrap: creates S3 bucket + DynamoDB table for OpenTofu remote state.
# Run once with local backend: tofu init && tofu apply
# Then configure main infra to use this backend.

terraform {
  backend "local" {
    path = "bootstrap.tfstate"
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  bucket_name = "9host-tofu-state-${local.account_id}"
  table_name  = "9host-tofu-state-lock"
}

resource "aws_s3_bucket" "state" {
  bucket = local.bucket_name

  tags = {
    Name = "9host-tofu-state"
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_dynamodb_table" "lock" {
  name         = local.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name = "9host-tofu-state-lock"
  }
}
