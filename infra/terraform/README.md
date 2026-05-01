# Terraform

This directory defines the shared DigitalOcean Droplet and firewall for the monorepo runtime. Normal production applies run through `.github/workflows/deploy.yml` after the GitHub `production` environment approval.

Expected workflow after local verification and GitHub repo creation:

```bash
cd infra/terraform
terraform init
terraform plan -var-file=terraform.tfvars
```

The desired steady-state target is `s-1vcpu-2gb`, but the existing Droplet has an 80 GiB disk and cannot resize in place to that 50 GiB plan. The Droplet resource sets `resize_disk = false`, `prevent_destroy = true`, and ignores size/networking/SSH/user-data drift so routine deploys do not retry the rejected shrink or replace an adopted Droplet for provider default drift. Size reduction is handled by the dedicated `Migrate Smaller Droplet` workflow, which creates a new small Droplet and promotes it only after DNS cutover. The deploy workflow imports an existing `platform-shared` Droplet before applying so a missing GitHub-side state file does not create a duplicate Droplet. The output `droplet_ip` is the value to use for Squarespace A records after a recreate/disaster-recovery event.
