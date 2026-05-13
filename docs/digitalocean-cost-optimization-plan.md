# DigitalOcean Cost Optimization Plan

Status: implemented.

Pricing snapshot: 2026-05-02. Prices are public USD list prices before tax, support, unusual bandwidth, prorated partial-month usage, and one-off snapshot storage.

## Current State As Of 2026-05-02

GitHub:

- Repository: `raniendu/platform`
- Default branch: `main`
- Deploy path: `.github/workflows/deploy.yml`
- Deploy mechanism: automatic `deploy.yml` run on pushes to `main`, plus manual `workflow_dispatch` redeploy support. The workflow performs Terraform adopt/plan/apply for the shared Droplet and firewall, SSHes to the Droplet, uploads the repo and `PLATFORM_ENV_FILE`, runs Docker Compose, force-recreates Caddy, then runs public smoke checks.

DigitalOcean:

| Resource | Current state |
| --- | --- |
| Droplet `platform-shared` | active, ID `568317243`, IP `174.138.71.121`, `s-1vcpu-2gb`, 1 vCPU, 2 GiB RAM, 50 GiB disk, backups enabled |
| Firewall `platform-shared-firewall` | active, ID `f08d6940-f470-47ce-8dba-ffad3ef16832`, attached to `platform-shared` |
| Old Droplet `prefect-server` | destroyed on 2026-04-27 without snapshot |
| Old App Platform app `dot-dev-app` | deleted on 2026-04-27 |
| Old firewall `prefect-server-firewall` | deleted on 2026-04-27 |
| Retired 4 GiB `platform-shared` Droplet | deleted on 2026-05-02 by run `25257362975` |
| Managed databases | none observed |
| Volumes | none observed |
| Load balancers | none observed |
| Standalone snapshots | none observed |

Current DNS:

```text
A      @        174.138.71.121
CNAME  www      raniendu.dev
A      prefect  174.138.71.121
A      paperclip 174.138.71.121
A      raman    174.138.71.121
A      flow     174.138.71.121
```

Current public smoke-check expectations:

```text
https://raniendu.dev/ -> 200
https://www.raniendu.dev/ -> 301
https://prefect.raniendu.dev/api/health -> 401
https://paperclip.raniendu.dev/ -> 404
https://raman.raniendu.dev/healthz -> 200
https://flow.raniendu.dev/ -> 404
```

`401` for Prefect is expected because Caddy basic auth protects that route. Raman returns `200` from `/healthz`. Paperclip and Flow return `404` while their production app flags are disabled.

## Current Cost

| Component | Monthly cost |
| --- | ---: |
| `platform-shared` Basic Droplet, `s-1vcpu-2gb` | $12.00 |
| Weekly Droplet backups, 20% | $2.40 |
| Firewalls | $0.00 |
| Managed DBs, App Platform apps, volumes, load balancers, snapshots | $0.00 |
| **Estimated steady state** | **$14.40** |

The May 2026 invoice can still include prorated usage for the retired 4 GiB Droplet before it was deleted.

## Completed Optimization Sequence

1. Removed old overlapping resources: `prefect-server`, `dot-dev-app`, and `prefect-server-firewall`.
2. Moved image builds off the Droplet and into GitHub Actions/GHCR.
3. Consolidated production Prefect and Airflow metadata databases into one `platform-postgres` container with separate app databases and roles.
4. Added personal-scale Airflow settings to reduce scheduler and task parallelism pressure.
5. Migrated from the old `s-2vcpu-4gb` 80 GiB Droplet to a new `s-1vcpu-2gb` 50 GiB Droplet through the reviewed `Migrate Smaller Droplet` GitHub Actions workflow.
6. Promoted the new Droplet back to canonical name `platform-shared`.
7. Deleted the retired 4 GiB Droplet after explicit approval.

The detailed migration record is in `docs/smaller-droplet-migration.md`.

## Why It Was Not An In-Place Resize

The old `platform-shared` host used an 80 GiB disk. DigitalOcean rejected moving it to `s-1vcpu-2gb` because that target plan has a 50 GiB disk. The implementation therefore used a new-Droplet migration instead of Terraform resizing.

Terraform still sets the desired size to `s-1vcpu-2gb`, imports the existing `platform-shared` Droplet before apply, and protects against duplicate or destructive Droplet plans.

## Remaining Cost Levers

Backups:

- Disabling weekly backups would save about $2.40/month.
- Keep backups enabled unless rollback requirements change.

Optional future `s-1vcpu-1gb` experiment:

- Estimated cost with weekly backups: about $7.20/month.
- Attempt only after at least one stable observation window on the 2 GiB host.
- Stop immediately on swap pressure, OOM kills, Airflow scheduler instability, Prefect worker missed runs, or deploy failures caused by host pressure.
- Rollback would require another reviewed migration or restoring from backup.

Architecture alternatives:

- Replacing Airflow with scheduled Prefect flows, cron, or serverless jobs could reduce runtime needs further.
- That would be a product/runtime change, not just an infrastructure optimization.

## Rules Going Forward

- Use `Deploy`, not `Migrate Smaller Droplet`, for routine releases.
- Keep all infrastructure write operations in reviewed PRs and GitHub Actions.
- Use local `doctl` for read-only inventory checks only.
- Do not reintroduce standalone DotDev App Platform, standalone Prefect Droplet, or standalone Airflow Terraform docs.
