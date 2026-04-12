# ------------------------------------------------------------------------------
# Task 1.99, 1.100b: Lambda + EventBridge for ACM cert issued → add CloudFront alias
# EventBridge rule on aws.acm cert status. On ACM Certificate Available (ISSUED):
# add alias to sites distribution, update domain PENDING_VALIDATION → ACTIVE. Zero polling.
# ------------------------------------------------------------------------------

data "archive_file" "acm_handler" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_acm_handler"
  output_path = "${path.module}/acm_handler.zip"

  excludes = [
    "__pycache__",
    "*.pyc",
    ".DS_Store",
  ]
}

resource "aws_iam_role" "acm_handler" {
  provider = aws.us_east_1

  name = "9host-acm-handler"

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
    Name = "9host-acm-handler"
  }
}

resource "aws_iam_role_policy" "acm_handler" {
  provider = aws.us_east_1

  name   = "9host-acm-handler"
  role   = aws_iam_role.acm_handler.id
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
        Resource = "arn:aws:logs:us-east-1:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/9host-acm-handler:*"
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem"
        ]
        Resource = [
          aws_dynamodb_table.main.arn,
          "${aws_dynamodb_table.main.arn}/index/*"
        ]
      },
      {
        Sid    = "CloudFrontCreate"
        Effect = "Allow"
        Action = [
          "cloudfront:CreateDistribution",
          "cloudfront:GetDistribution",
          "cloudfront:GetDistributionConfig",
          "cloudfront:UpdateDistribution"
        ]
        Resource = "*"
      },
      {
        Sid    = "ACM"
        Effect = "Allow"
        Action = [
          "acm:DescribeCertificate"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_lambda_function" "acm_handler" {
  provider = aws.us_east_1

  function_name = "9host-acm-handler"
  role          = aws_iam_role.acm_handler.arn
  handler       = "main.lambda_handler"
  runtime       = "python3.12"

  filename         = data.archive_file.acm_handler.output_path
  source_code_hash = data.archive_file.acm_handler.output_base64sha256

  memory_size = 256
  timeout     = 60

  environment {
    variables = {
      CLOUDFRONT_SITES_DISTRIBUTION_ID         = aws_cloudfront_distribution.sites.id
      DYNAMODB_TABLE                           = aws_dynamodb_table.main.name
      SITES_BUCKET_DOMAIN                      = aws_s3_bucket.sites.bucket_regional_domain_name
      MEDIA_BUCKET_DOMAIN                      = aws_s3_bucket.media.bucket_regional_domain_name
      CLOUDFRONT_OAC_ID                        = aws_cloudfront_origin_access_control.frontend.id
      CLOUDFRONT_CUSTOM_DOMAIN_FUNCTION_ARN    = aws_cloudfront_function.custom_domain.arn
      CLOUDFRONT_MEDIA_FUNCTION_ARN            = aws_cloudfront_function.media_content.arn
    }
  }

  tags = {
    Name = "9host-acm-handler"
  }
}

resource "aws_cloudwatch_event_rule" "acm_certificate_available" {
  provider = aws.us_east_1

  name        = "9host-acm-certificate-available"
  description = "Trigger when ACM certificate becomes available (Task 1.99, 1.100b)"

  event_pattern = jsonencode({
    source      = ["aws.acm"]
    detail-type = ["ACM Certificate Available"]
  })
}

resource "aws_cloudwatch_event_target" "acm_handler" {
  provider = aws.us_east_1

  rule      = aws_cloudwatch_event_rule.acm_certificate_available.name
  target_id = "9host-acm-handler"
  arn       = aws_lambda_function.acm_handler.arn
}

resource "aws_lambda_permission" "acm_eventbridge" {
  provider = aws.us_east_1

  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.acm_handler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.acm_certificate_available.arn
}
