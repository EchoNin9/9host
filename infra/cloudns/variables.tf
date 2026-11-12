variable "domains" {
  description = "List of base domains (e.g. [\"echo9.net\"]). Override or use remote state."
  type        = list(string)
  default     = []
}

variable "aws_region" {
  description = "AWS region (for remote state)."
  type        = string
  default     = "us-east-1"
}
