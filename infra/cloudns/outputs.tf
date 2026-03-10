output "zone_ids" {
  description = "CloudNS zone IDs by domain"
  value       = { for d, z in cloudns_dns_zone.zone : d => z.id }
}
