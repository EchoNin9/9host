variable "aws_region" {
  description = "AWS region for resources."
  type        = string
  default     = "us-east-1"
}

variable "github_org_repo" {
  description = "GitHub org/repo for OIDC trust (e.g. EchoNin9/9host)."
  type        = string
}

variable "domain" {
  description = "Primary domain (e.g. echo9.net)."
  type        = string
  default     = "echo9.net"
}
