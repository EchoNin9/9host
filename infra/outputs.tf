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
