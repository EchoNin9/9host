output "route53_zone_id" {
  description = "Route 53 hosted zone ID."
  value       = aws_route53_zone.main.zone_id
}

output "route53_name_servers" {
  description = "Nameservers for domain delegation. Add these NS records at your registrar."
  value       = aws_route53_zone.main.name_servers
}

output "acm_certificate_arn" {
  description = "ACM certificate ARN (status Pending until DNS validation completes)."
  value       = aws_acm_certificate.main.arn
}
