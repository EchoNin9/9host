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

# T-08: Public landing page served by the sites distribution at (www.)<landing_domain>.
variable "landing_domain" {
  description = "Bare landing hostname served by the sites distribution (plus www.). Must be one of var.domains."
  type        = string
  default     = "echo9.net"
}

variable "serve_landing_domain" {
  description = "Attach <landing_domain> and www.<landing_domain> as aliases on the sites distribution. Enable only after those aliases are removed from any other CloudFront distribution."
  type        = bool
  default     = false
}

variable "landing_site" {
  description = "Optional landing site mapping written to 9host-site-hosts-kvs for <landing_domain> and www.<landing_domain>. null = no KVS keys."
  type = object({
    tenant  = string
    site_id = string
  })
  default = null
}
