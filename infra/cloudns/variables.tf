variable "domain" {
  description = "Primary domain (e.g. echo9.net)."
  type        = string
  default     = "echo9.net"
}

variable "aws_region" {
  description = "AWS region (for remote state)."
  type        = string
  default     = "us-east-1"
}

# DEPRECATED: Credentials come from AWS Secrets Manager (9host-cloudns).
# These exist only to accept (and ignore) legacy tfvars. Remove from your tfvars.
variable "cloudns_auth_id" {
  description = "DEPRECATED: Use Secrets Manager. Ignored."
  type        = number
  default     = 0
  sensitive   = true
}

variable "cloudns_password" {
  description = "DEPRECATED: Use Secrets Manager. Ignored."
  type        = string
  default     = ""
  sensitive   = true
}
