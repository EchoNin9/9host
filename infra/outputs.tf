output "acm_certificate_arn" {
  description = "ACM certificate ARN (status Pending until DNS validation completes in CloudNS)."
  value       = aws_acm_certificate.main.arn
}

# Add these CNAME records to CloudNS for ACM validation
output "acm_validation_records" {
  description = "Add these CNAME records to CloudNS (echo9.net zone) for ACM validation."
  value = [
    for dvo in aws_acm_certificate.main.domain_validation_options : {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      value  = dvo.resource_record_value
      domain = dvo.domain_name
    }
  ]
}

# ------------------------------------------------------------------------------
# Add these as GitHub repo variables (Settings → Secrets and variables → Actions)
# ------------------------------------------------------------------------------
output "github_var_aws_role_arn_staging" {
  description = "Set as GitHub repo variable AWS_ROLE_ARN_STAGING"
  value       = aws_iam_role.github_staging.arn
}

output "github_var_aws_role_arn_production" {
  description = "Set as GitHub repo variable AWS_ROLE_ARN_PRODUCTION"
  value       = aws_iam_role.github_production.arn
}

output "dynamodb_table_name" {
  description = "9host-main DynamoDB table name"
  value       = aws_dynamodb_table.main.name
}

output "dynamodb_table_arn" {
  description = "9host-main DynamoDB table ARN"
  value       = aws_dynamodb_table.main.arn
}

# ------------------------------------------------------------------------------
# CloudFront + S3 (Task 1.8)
# ------------------------------------------------------------------------------
output "cloudfront_staging_distribution_id" {
  description = "CloudFront staging distribution ID (for cache invalidation)"
  value       = aws_cloudfront_distribution.staging.id
}

output "cloudfront_staging_domain" {
  description = "CloudFront staging distribution domain (add CNAME stage.echo9.net -> this in CloudNS)"
  value       = aws_cloudfront_distribution.staging.domain_name
}

output "cloudfront_staging_url" {
  description = "Staging frontend URL (after DNS)"
  value       = "https://stage.${var.domain}"
}

output "cloudfront_production_distribution_id" {
  description = "CloudFront production distribution ID (for cache invalidation)"
  value       = aws_cloudfront_distribution.production.id
}

output "cloudfront_production_domain" {
  description = "CloudFront production distribution domain (add CNAME prod.echo9.net -> this in CloudNS)"
  value       = aws_cloudfront_distribution.production.domain_name
}

output "cloudfront_production_url" {
  description = "Production frontend URL (after DNS)"
  value       = "https://prod.${var.domain}"
}

output "s3_frontend_staging_bucket" {
  description = "S3 bucket for staging frontend (aws s3 sync dist/ s3://this-bucket/)"
  value       = aws_s3_bucket.frontend_staging.id
}

output "s3_frontend_production_bucket" {
  description = "S3 bucket for production frontend"
  value       = aws_s3_bucket.frontend_production.id
}

# ------------------------------------------------------------------------------
# Cognito (Task 1.9) — for frontend auth config
# ------------------------------------------------------------------------------
output "cognito_user_pool_id" {
  description = "Cognito User Pool ID (9host-user-pool)"
  value       = aws_cognito_user_pool.main.id
}

output "cognito_user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = aws_cognito_user_pool.main.arn
}

output "cognito_client_id" {
  description = "Cognito App Client ID for frontend"
  value       = aws_cognito_user_pool_client.frontend.id
}

output "cognito_domain" {
  description = "Cognito hosted UI domain (e.g. 9host-auth.auth.us-east-1.amazoncognito.com)"
  value       = "${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com"
}

output "cognito_issuer_url" {
  description = "Cognito issuer URL for OIDC"
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
}

# ------------------------------------------------------------------------------
# API Gateway (Task 1.10)
# ------------------------------------------------------------------------------
output "api_gateway_invoke_url" {
  description = "API Gateway HTTP API invoke URL (e.g. https://xxx.execute-api.us-east-1.amazonaws.com)"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "api_gateway_id" {
  description = "API Gateway HTTP API ID"
  value       = aws_apigatewayv2_api.main.id
}

# ------------------------------------------------------------------------------
# CloudNS credentials (Secrets Manager)
# ------------------------------------------------------------------------------
output "cloudns_secret_arn" {
  description = "ARN of Secrets Manager secret for CloudNS credentials. Set value via: aws secretsmanager put-secret-value --secret-id 9host-cloudns --secret-string '{\"auth_id\":12345,\"password\":\"xxx\"}'"
  value       = aws_secretsmanager_secret.cloudns.arn
}
