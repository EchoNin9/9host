variable "domain" {
  description = "Primary domain (e.g. echo9.net)."
  type        = string
  default     = "echo9.net"
}

variable "cloudns_auth_id" {
  description = "ClouDNS API auth-id (from Account Settings > API)."
  type        = number
  sensitive   = true
}

variable "cloudns_password" {
  description = "ClouDNS API password (auth-password)."
  type        = string
  sensitive   = true
}
