# AGENTS Guide: Airflow on DigitalOcean

## Purpose and Scope

This repository manages Apache Airflow deployment and its DigitalOcean infrastructure using Terraform and GitHub Actions.

Infrastructure boundary for this repo:

- Terraform-managed Airflow droplet, firewall, and optional DNS record
- CI/CD deployment pipeline that applies Terraform and deploys app code

Out of scope:

- Unrelated DigitalOcean services/resources not managed by this Terraform state

## Canonical Infra Toggle

Use `terraform/deployment.auto.tfvars` as the single source of truth:

```hcl
infra_enabled = false
```

- `false`: pause infrastructure (Terraform destroys managed resources)
- `true`: provision/reprovision managed resources

## Safe Pause Procedure

1. Confirm `terraform/deployment.auto.tfvars` has `infra_enabled = false`.
2. Commit and push to `main`.
3. Verify GitHub Actions `Deploy to Digital Ocean` workflow:
   - Terraform apply runs successfully.
   - Deploy job is skipped.
4. Verify Airflow resources are removed from DigitalOcean.

## Safe Resume Procedure

1. Set `infra_enabled = true` in `terraform/deployment.auto.tfvars`.
2. Commit and push to `main`.
3. Verify workflow:
   - Terraform apply creates resources.
   - Deploy job runs.
4. Verify a new droplet IP is produced and Airflow is reachable.

## Resource Safety Rules

Only destroy resources tracked by this repository's Terraform state.

- Preferred destructive path: `terraform apply` with `infra_enabled=false`
- Avoid ad hoc manual deletions when Terraform can perform the change
- Never delete shared/unrelated resources

Known non-target resources that must not be touched:

- Droplet: `prefect-server`
- DigitalOcean App Platform apps (for example `babamuskbot`, `dot-dev-app`)

## Verification Commands and Checks

Before pause/resume apply:

```bash
cd terraform
terraform state list
terraform plan
```

After pause:

```bash
cd terraform
terraform output
```

Expected: no active droplet outputs (`droplet_ip` empty), deploy job skipped in CI.

Use DigitalOcean dashboard/API to confirm:

- `airflow-server` is removed when paused
- unrelated resources remain unchanged

## Documentation Maintenance Rule

Any infrastructure workflow change must update all of:

- `README.md`
- `terraform/README.md`
- `AGENTS.md`
