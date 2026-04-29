# Terraform

This directory defines the shared DigitalOcean Droplet and firewall for the monorepo runtime. Normal production applies run through `.github/workflows/deploy.yml` after the GitHub `production` environment approval.

Expected workflow after local verification and GitHub repo creation:

```bash
cd infra/terraform
terraform init
terraform plan -var-file=terraform.tfvars
```

The routine deploy target remains `s-2vcpu-4gb` until the explicit smaller-Droplet migration is ready. The existing Droplet has an 80 GiB disk and cannot resize in place to `s-1vcpu-2gb`, whose disk is smaller. The Droplet resource still sets `resize_disk = false`, `prevent_destroy = true`, and the deploy workflow imports an existing `platform-shared` Droplet before applying so a missing GitHub-side state file does not create a duplicate Droplet. The output `droplet_ip` is the value to use for Squarespace A records after a recreate/disaster-recovery event.
