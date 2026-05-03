# Terraform

This directory defines the shared DigitalOcean Droplet and firewall for the monorepo runtime. Normal production applies run through `.github/workflows/deploy.yml` after the GitHub `production` environment approval.

Expected workflow after local verification and GitHub repo creation:

```bash
cd infra/terraform
terraform init
terraform plan -var-file=terraform.tfvars
```

The desired steady-state target is `s-1vcpu-2gb`, which is the current production size after the completed May 2026 smaller-Droplet migration. The Droplet resource sets `resize_disk = false`, `prevent_destroy = true`, and ignores size/networking/SSH/user-data drift so routine deploys adopt the existing Droplet instead of replacing it for provider default drift. The deploy workflow imports an existing `platform-shared` Droplet before applying so a missing GitHub-side state file does not create a duplicate Droplet. The output `droplet_ip` is the value to use for Squarespace A records after a recreate/disaster-recovery event.

Do not run Terraform apply locally for production infrastructure. Local Terraform usage is for review and planning only; production writes run through reviewed PRs and GitHub Actions.
