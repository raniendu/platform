# Terraform

This directory defines the future shared DigitalOcean Droplet for the monorepo runtime. Do not run `terraform apply` until the Terraform approval gate.

Expected workflow after local verification and GitHub repo creation:

```bash
cd infra/terraform
terraform init
terraform plan -var-file=terraform.tfvars
```

The initial Droplet size is `s-2vcpu-4gb`. The output `droplet_ip` is the value to use for Squarespace A records after the DNS cutover gate.

