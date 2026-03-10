output "zone_id" {
  description = "CloudNS zone ID for echo9.net"
  value       = cloudns_dns_zone.echo9_net.id
}
