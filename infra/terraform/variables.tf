variable "do_token" {
  description = "DigitalOcean API token. Prefer TF_VAR_do_token from a secret store."
  type        = string
  sensitive   = true
}

variable "region" {
  description = "DigitalOcean region for the shared platform Droplet."
  type        = string
  default     = "nyc3"
}

variable "droplet_size" {
  description = "Initial shared Droplet size."
  type        = string
  default     = "s-2vcpu-4gb"
}

variable "ssh_key_fingerprints" {
  description = "DigitalOcean SSH key fingerprints allowed to access the Droplet."
  type        = list(string)
}

variable "allowed_ssh_cidrs" {
  description = "CIDR ranges allowed to SSH into the Droplet."
  type        = list(string)
  default     = []
}

variable "droplet_name" {
  description = "Name of the shared Droplet."
  type        = string
  default     = "platform-shared"
}

variable "project_name" {
  description = "DigitalOcean project name tag used for grouping resources."
  type        = string
  default     = "platform"
}

