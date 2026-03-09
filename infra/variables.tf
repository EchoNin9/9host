variable "aws_region" {
  description = "AWS region for resources."
  type        = string
  default     = "us-east-1"
}

variable "domain" {
  description = "Primary domain (e.g. echo9.net)."
  type        = string
  default     = "echo9.net"
}
