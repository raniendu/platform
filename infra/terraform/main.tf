provider "digitalocean" {
  token = var.do_token
}

resource "digitalocean_droplet" "platform" {
  image       = "ubuntu-24-04-x64"
  name        = var.droplet_name
  region      = var.region
  size        = var.droplet_size
  resize_disk = false
  backups     = var.enable_backups
  ssh_keys    = var.ssh_key_fingerprints
  tags        = [var.project_name, "shared-runtime"]

  user_data = file("${path.module}/cloud-init.yaml")

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      image,
      ssh_keys,
      user_data,
    ]
  }

  dynamic "backup_policy" {
    for_each = var.enable_backups ? [1] : []
    content {
      plan    = var.backup_policy_plan
      weekday = var.backup_policy_weekday
      hour    = var.backup_policy_hour
    }
  }
}

resource "digitalocean_firewall" "platform" {
  name        = "${var.droplet_name}-firewall"
  droplet_ids = [digitalocean_droplet.platform.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  dynamic "inbound_rule" {
    for_each = var.allowed_ssh_cidrs
    content {
      protocol         = "tcp"
      port_range       = "22"
      source_addresses = [inbound_rule.value]
    }
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}
