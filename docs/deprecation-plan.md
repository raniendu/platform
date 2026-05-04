# Old Infrastructure Deprecation Record

This document is now a completion record. The old DigitalOcean and App Platform resources for the pre-monorepo deployment have been removed.

## Current Replacement

The consolidated platform is:

- Droplet: `platform-shared`
- IP: `174.138.71.121`
- Size: `s-1vcpu-2gb`
- Firewall: `platform-shared-firewall`
- Public routes:
  - `https://raniendu.dev`
  - `https://www.raniendu.dev` -> redirect to `https://raniendu.dev`
  - `https://prefect.raniendu.dev`
  - `https://paperclip.raniendu.dev`
  - `https://flow.raniendu.dev`

## Completed Decommissioning

| Resource | Final state |
| --- | --- |
| Old Droplet `prefect-server` | destroyed on 2026-04-27 without snapshot |
| Old App Platform app `dot-dev-app` | deleted on 2026-04-27 |
| Old firewall `prefect-server-firewall` | deleted on 2026-04-27 |
| Retired 4 GiB `platform-shared` Droplet | deleted on 2026-05-02 by `Migrate Smaller Droplet` run `25257362975` |
| Managed databases | none observed |
| Volumes | none observed |
| Load balancers | none observed |
| Standalone snapshots | none observed |

## Current Verification

Expected public smoke checks:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://raniendu.dev/
curl -sS -o /dev/null -w '%{http_code}\n' https://www.raniendu.dev/
curl -sS -o /dev/null -w '%{http_code}\n' https://prefect.raniendu.dev/api/health
curl -sS -o /dev/null -w '%{http_code}\n' https://paperclip.raniendu.dev/
curl -sS -o /dev/null -w '%{http_code}\n' https://flow.raniendu.dev/
```

Expected: `200`, `301`, `401`, `401`, `200`.

`401` for Prefect and Paperclip is expected because Caddy basic auth protects those routes.

Read-only inventory checks should show only the shared runtime resources for this stack:

```bash
doctl compute droplet list
doctl apps list
doctl databases list
doctl compute volume list
doctl compute load-balancer list
doctl compute snapshot list
```

## Rules Going Forward

- `raniendu/platform` is the source of truth for production deployment.
- Do not reintroduce standalone DotDev App Platform, standalone Prefect Droplet, or standalone Airflow Terraform instructions.
- Do not run local DigitalOcean write operations for infra changes. Use reviewed PRs and GitHub Actions.
- Keep `DIGITALOCEAN_ACCESS_TOKEN`, `DO_SSH_KEY_FINGERPRINTS`, `ALLOWED_SSH_CIDRS`, `PLATFORM_ENV_FILE`, `PLATFORM_SSH_PORT`, `PLATFORM_SSH_PRIVATE_KEY`, and `PLATFORM_SSH_USER` for the shared deploy workflow.
