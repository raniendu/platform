# Smaller Droplet Migration

Status: completed on 2026-05-02.

Production now runs on:

- Droplet: `platform-shared`
- IP: `174.138.71.121`
- Size: `s-1vcpu-2gb`
- Disk: 50 GiB

The old 4 GiB Droplet was renamed to `platform-shared-retired-25253252730` during promotion and then deleted by the `decommission_retired` phase.

## Completed Runs

| Phase | GitHub Actions run | Result |
| --- | --- | --- |
| `stage` | `25219688318` | Created/staged `platform-shared-small`, migrated Postgres and Caddy data, smoke-tested the new IP |
| `promote` | `25253252730` | Renamed `platform-shared-small` to canonical `platform-shared`; renamed old Droplet to `platform-shared-retired-25253252730` |
| `decommission_retired` | `25257362975` | Deleted `platform-shared-retired-25253252730` |

## Why The Workflow Exists

The old `platform-shared` Droplet was `s-2vcpu-4gb` with an 80 GiB disk. DigitalOcean would not resize that Droplet in place to `s-1vcpu-2gb` because the target plan has a 50 GiB disk. The safe path was a reviewed GitHub Actions migration that created a new smaller Droplet, copied data, cut DNS over manually, promoted the new host, and deleted the retired host only after explicit approval.

Keep `.github/workflows/migrate-smaller-droplet.yml` as the audited pattern for future new-Droplet migrations. Use `.github/workflows/deploy.yml` for routine production releases.

All DigitalOcean write operations for future migrations must run from GitHub Actions after review and approval. Local `doctl` usage is read-only only.

## Current Routine Deploy Safety

The normal `Deploy` workflow:

- imports the existing `platform-shared` Droplet/firewall before Terraform apply;
- refuses Droplet delete/replace plans;
- refuses duplicate matching Droplets;
- refuses to create a second Droplet when one already exists;
- refuses routine deploys while a Droplet named `platform-shared-small` exists.

`platform-shared-small` should not exist during steady state. If it does, a staged migration is incomplete and must be promoted or rolled back before routine deploys continue.

## Future Migration Runbook

Use this only for a future new-Droplet migration, not for routine deploys.

### 1. Stage

Run `Migrate Smaller Droplet` with:

- `phase`: `stage`
- `confirmation`: `stage-platform-shared-to-s-1vcpu-2gb`
- `retired_droplet_name`: blank

The stage phase creates or reuses one `platform-shared-small` Droplet, attaches it to the firewall, copies repository and environment data, migrates Prefect, Airflow, and Paperclip Postgres data, copies Caddy data, copies Raman state, starts services in phases, and smoke-tests the public routes with `curl --resolve`.

### 2. DNS Cutover

Manually update Squarespace A records to the staged Droplet IP:

- `raniendu.dev`
- `prefect.raniendu.dev`
- `paperclip.raniendu.dev`
- `raman.raniendu.dev`
- `flow.raniendu.dev`

Keep `www.raniendu.dev` as a CNAME to `raniendu.dev`.

### 3. Promote

After DNS resolves to the staged Droplet and public smoke checks pass, run:

- `phase`: `promote`
- `confirmation`: `promote-platform-shared-small-to-platform-shared`
- `retired_droplet_name`: blank

The promote phase verifies public traffic reaches the staged host, runs smoke checks, renames the old Droplet to `platform-shared-retired-<run-id>`, and renames the staged Droplet to `platform-shared`.

### 4. Decommission

After the promoted Droplet is accepted in production and explicit approval is recorded, run:

- `phase`: `decommission_retired`
- `confirmation`: `decommission-<retired-droplet-name>`
- `retired_droplet_name`: `<retired-droplet-name>` from the promote summary

The decommission phase verifies public smoke checks, detaches the retired Droplet from the firewall, and deletes it. This is what removes the old Droplet cost.

## Rollback

Before `promote`, rollback is DNS-first:

1. Point Squarespace DNS records back to the previous production Droplet IP.
2. Run `Migrate Smaller Droplet` with:
   - `phase`: `rollback_stage`
   - `confirmation`: `rollback-platform-shared-small`
   - `retired_droplet_name`: blank
3. Verify public smoke checks: `200`, `301`, `401`, `401`, `200`, `200`.

After `promote` but before `decommission_retired`, rollback is no longer DNS-only because the canonical resource names have changed.

After `decommission_retired`, rollback requires restoring from the latest Droplet backup/snapshot or an application-level database backup.
