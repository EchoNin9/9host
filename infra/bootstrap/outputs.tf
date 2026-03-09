output "state_bucket" {
  description = "S3 bucket for OpenTofu state"
  value       = aws_s3_bucket.state.id
}

output "lock_table" {
  description = "DynamoDB table for state locking"
  value       = aws_dynamodb_table.lock.name
}

output "backend_config" {
  description = "Add to infra backend block or -backend-config"
  value = {
    bucket         = aws_s3_bucket.state.id
    key            = "9host/terraform.tfstate"
    region         = var.aws_region
    dynamodb_table = aws_dynamodb_table.lock.name
  }
}
