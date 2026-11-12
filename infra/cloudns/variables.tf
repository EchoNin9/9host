variable "domains" {
  description = "List of base domains (e.g. [\"echo9.net\", \"echo9.ca\"]). Override or use remote state."
  type        = list(string)
  default     = []
}

variable "aws_region" {
  description = "AWS region (for remote state)."
  type        = string
  default     = "us-east-1"
}

# Set to false when records already exist in CloudNS and import fails (provider bug with priority field).
# Records will be managed manually. Zone is still managed by Terraform.
variable "manage_records" {
  description = "Create/manage DNS records (ACM validation, stage, prod). Set false if records exist and import fails."
  type        = bool
  default     = true
}

# T-08: app / sites-origin / tools records. Independent of manage_records (legacy records).
variable "manage_edge_records" {
  description = "Create/manage T-08 edge records (app.*, sites-origin, tools WR)."
  type        = bool
  default     = true
}

variable "primary_domain" {
  description = "Zone for single-zone T-08 records (sites-origin, tools). Must be in domains."
  type        = string
  default     = "echo9.net"
}
