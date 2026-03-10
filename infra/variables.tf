variable "aws_region" {
  description = "AWS region for resources."
  type        = string
  default     = "us-east-1"
}

variable "github_org_repo" {
  description = "GitHub org/repo for OIDC trust (e.g. EchoNin9/9host)."
  type        = string
}

variable "domains" {
  description = "List of base domains for stage/prod. Add echo9.ca after CloudNS zone + validation records exist."
  type        = list(string)
  default     = ["echo9.net"]
}
