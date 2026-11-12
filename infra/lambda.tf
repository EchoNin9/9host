# ------------------------------------------------------------------------------
# 9host API Lambda — Task 1.10
# Packages api/ handlers, uses tenant middleware. Prefix: 9host.
# ------------------------------------------------------------------------------

# T-07: Cloudflare for SaaS API credentials secret (referenced by name; value is
# written out-of-band, never by OpenTofu).
locals {
  cloudflare_secret_name = "9host-cloudflare"
}

# Requires the build step first: scripts/build-lambda-package.sh (creates infra/.build/api_lambda).
# If that directory is missing, `tofu validate/plan` fails with a "source_dir ... no such file" error.
data "archive_file" "api" {
  type        = "zip"
  source_dir  = "${path.module}/.build/api_lambda"
  output_path = "${path.module}/api.zip"

  excludes = [
    "__pycache__",
    "*.pyc",
    ".DS_Store",
  ]
}

resource "aws_iam_role" "api_lambda" {
  name = "9host-api-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "9host-api-lambda"
  }
}

resource "aws_iam_role_policy" "api_lambda" {
  name = "9host-api-lambda"
  role = aws_iam_role.api_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/9host-api:*"
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:ConditionCheckItem"
        ]
        Resource = [
          aws_dynamodb_table.main.arn,
          "${aws_dynamodb_table.main.arn}/index/*"
        ]
      },
      {
        Sid    = "Cognito"
        Effect = "Allow"
        Action = [
          "cognito-idp:GetUser",
          "cognito-idp:AdminGetUser",
          "cognito-idp:AdminListGroupsForUser",
          "cognito-idp:ListUsers",
          "cognito-idp:ListUsersInGroup"
        ]
        Resource = aws_cognito_user_pool.main.arn
      },
      {
        Sid    = "SecretsManager"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          aws_secretsmanager_secret.stripe.arn,
          aws_secretsmanager_secret.jwt_signing.arn,
          aws_secretsmanager_secret.cloudns.arn
        ]
      },
      {
        Sid    = "S3SitesMedia"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:HeadObject",
          "s3:DeleteObject",
          "s3:CopyObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.sites.arn,
          "${aws_s3_bucket.sites.arn}/*",
          aws_s3_bucket.media.arn,
          "${aws_s3_bucket.media.arn}/*"
        ]
      },
      {
        Sid    = "SiteHostsKVS"
        Effect = "Allow"
        Action = [
          "cloudfront-keyvaluestore:DescribeKeyValueStore",
          "cloudfront-keyvaluestore:PutKey",
          "cloudfront-keyvaluestore:DeleteKey",
          "cloudfront-keyvaluestore:ListKeys"
        ]
        Resource = aws_cloudfront_key_value_store.site_hosts.arn
      },
      {
        # T-07: Cloudflare for SaaS credentials (zone_id, api_token). Secret is created
        # out-of-band (docs/UNATTENDED_ORCHESTRATION.md §5); "-*" matches the ARN suffix.
        Sid      = "CloudflareSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${local.cloudflare_secret_name}-*"
      }
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name = "9host-api"
  role          = aws_iam_role.api_lambda.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.12"

  filename         = data.archive_file.api.output_path
  source_code_hash = data.archive_file.api.output_base64sha256

  memory_size = 256
  timeout     = 30

  environment {
    variables = {
      DYNAMODB_TABLE          = aws_dynamodb_table.main.name
      DOMAINS                 = join(",", var.domains)
      USER_POOL_ID            = aws_cognito_user_pool.main.id
      STRIPE_SECRET_ARN       = aws_secretsmanager_secret.stripe.arn
      JWT_SECRET_ARN          = aws_secretsmanager_secret.jwt_signing.arn
      CLOUDFRONT_SITES_DOMAIN = aws_cloudfront_distribution.sites.domain_name
      CLOUDNS_SECRET_ARN      = aws_secretsmanager_secret.cloudns.arn
      CLOUDNS_ZONE            = var.domains[0]
      CLOUDNS_CF_TARGET       = aws_cloudfront_distribution.sites.domain_name
      SITE_HOSTS_KVS_ARN      = aws_cloudfront_key_value_store.site_hosts.arn
      CLOUDFLARE_SECRET_ARN   = local.cloudflare_secret_name
    }
  }

  tags = {
    Name = "9host-api"
  }
}
