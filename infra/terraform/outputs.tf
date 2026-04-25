output "droplet_ip" {
  description = "Public IPv4 address for Squarespace A records after cutover approval."
  value       = digitalocean_droplet.platform.ipv4_address
}

output "droplet_name" {
  description = "Shared platform Droplet name."
  value       = digitalocean_droplet.platform.name
}

output "firewall_id" {
  description = "DigitalOcean firewall ID used by the deploy workflow for temporary runner SSH access."
  value       = digitalocean_firewall.platform.id
}
