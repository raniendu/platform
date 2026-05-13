# Operations

Use this runbook after a deploy, during incident response, or before production
maintenance. Use [deployment](deployment.md) for the release workflow and
[rollback](rollback.md) when the answer is to move back to a known-good commit
or backup.

## Triage Order

1. Check GitHub Actions for the latest CI/deploy result.
2. Check public health endpoints to identify the affected route.
3. Check Caddy logs if multiple hostnames fail or TLS/routing looks wrong.
4. Check the app container logs if only one service fails.
5. Check Docker container health and restart counts before restarting anything.
6. Preserve logs and state before deleting volumes or containers.

## Logs

Local:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f
```

Production:

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production logs -f
```

Filter by service name when possible:

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production logs -f caddy
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production logs -f prefect-worker
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production logs -f paperclip
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production logs -f raman
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production logs -f homi
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production logs -f vikram
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production logs -f airflow-scheduler
```

## Traces

Local Jaeger v2:

```bash
RAMAN_OBSERVABILITY_ENABLED=true docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build raman jaeger
open http://localhost:16686
```

Production Jaeger is enabled when `DEPLOY_OBSERVABILITY=true` is set in
`deploy/apps.prod.env`; the deploy workflow writes
`RAMAN_OBSERVABILITY_ENABLED` from that flag so production Raman exports traces
to `http://jaeger:4318`. The Jaeger UI is exposed at
`https://jaeger.raniendu.dev` behind Caddy basic auth using the Prefect basic
auth credentials. Add the `jaeger` DNS A record before deploying this route.

## Restarts

Restart one service:

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production restart prefect-worker
```

Restart Paperclip:

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production restart paperclip
```

Pull and restart the current production images:

```bash
bash deploy/scripts/render-prod-caddy.sh deploy/apps.prod.env deploy/caddy/prod-sites
COMPOSE_PROFILES=dotdev,prefect,raman docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production pull postgres caddy dotdev prefect-server prefect-worker raman
COMPOSE_PROFILES=dotdev,prefect,raman docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production up -d --no-build
```

Production deploys start automatically after pushes to `main`. To redeploy the current `main` manually:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

The GitHub workflow applies Terraform, handles temporary SSH firewall access, pulls SHA-pinned images, recreates Caddy, waits for Caddy and DotDev readiness, runs public smoke checks, and cleans up temporary access. Public smoke checks continue after individual failures and then dump Caddy/DotDev diagnostics before the job exits.

## Production App Flags

Production app launch is controlled by `deploy/apps.prod.env`.

```env
DEPLOY_DOTDEV=true
DEPLOY_PREFECT=true
DEPLOY_FLOW=false
DEPLOY_PAPERCLIP=false
DEPLOY_RAMAN=true
DEPLOY_HOMI=false
DEPLOY_VIKRAM=false
```

Change a flag in a PR and merge to `main`; the `Deploy` workflow starts from that push. Disabled apps are removed from the running container set and their public hostnames return `404`, but their code, config, database data, and Docker volumes are preserved. Re-enabling Paperclip does not require another admin invite unless the Paperclip database or `paperclip-data` volume has been reset.

## Temporary SSH Access

Use the `Temporary SSH Access` workflow only when an interactive host session is required and the DigitalOcean web console is unavailable. Pass a single administrator `/32` CIDR, keep the window short, and let the workflow close the rule automatically. Do not use this workflow to add broad CIDRs such as `0.0.0.0/0`.

## Emergency Droplet Recovery

If the Droplet accepts TCP connections but SSH or HTTPS handshakes time out, the host may be under memory pressure during startup. Use the `Resize Droplet` workflow to temporarily move `platform-shared` to `s-2vcpu-4gb` without resizing disk, run `Deploy` to apply the production app flags, then use `Resize Droplet` again to return to `s-1vcpu-2gb` after smoke checks pass.

The resize workflow is production-gated, only accepts `platform-shared`, and does not use the irreversible `--resize-disk` option.

The `s-1vcpu-2gb` migration is complete. Use `Deploy` for routine releases. Keep `Migrate Smaller Droplet` as the audited pattern for future new-Droplet migrations; do not use local `doctl` for write operations.

## Health Checks

```bash
curl -I https://raniendu.dev/
curl https://raniendu.dev/healthz
curl -I https://www.raniendu.dev/
curl -I https://prefect.raniendu.dev/
curl -I https://raman.raniendu.dev/healthz
curl -I https://paperclip.raniendu.dev/ # expected 404 while disabled
curl -I https://flow.raniendu.dev/      # expected 404 while disabled
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production ps
```

Homi and Vikram public checks are only expected after their DNS records exist and `DEPLOY_HOMI=true` or `DEPLOY_VIKRAM=true`.

Expected disabled-app responses are part of the signal: Paperclip and Flow
return `404` while their production flags are false. A `404` for Raman, DotDev,
Prefect, or Jaeger while their flags are true usually means Caddy rendering,
profiles, or DNS should be checked before app internals.

Prefect API health:

```bash
curl https://prefect.raniendu.dev/api/health
```

Paperclip direct health from the host:

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production exec paperclip curl --fail --header 'Host: paperclip.raniendu.dev' http://localhost:3100/api/health
```

## Paperclip Browser Login

The first browser prompt for `https://paperclip.raniendu.dev` is Caddy basic auth, not the Paperclip app login. Use the Paperclip-specific values from `.env.production.credentials`:

```bash
grep '^PAPERCLIP_BASIC_AUTH_' .env.production.credentials
```

Do not use `PAPERCLIP_BETTER_AUTH_SECRET` for this prompt. That value is an internal Paperclip secret from `.env.production.generated`, not a human password.

## Paperclip Admin Bootstrap

Generate the first admin invite only in an interactive local or host shell after Paperclip is running:

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production exec paperclip pnpm paperclipai auth bootstrap-ceo --config /etc/paperclip/config.json --base-url https://paperclip.raniendu.dev
```

Treat the invite URL as a credential and do not paste it into GitHub Actions logs, issues, docs, or chat.

If the DigitalOcean web console and direct SSH are unavailable, use the `Paperclip Bootstrap Admin` workflow. It runs the bootstrap command over the existing deploy SSH key, stores command output in a one-day GitHub Actions artifact, and keeps the invite out of logs. Download the artifact locally and delete it after redeeming the invite.

## Backups

Back up named volumes before risky deploys:

- `postgres-data`
- `caddy-data`
- `caddy-config`
- `paperclip-data`
- `raman-state`
- `homi-state`
- `vikram-state`

Paperclip metadata lives in the `paperclip` database inside `postgres-data`; Paperclip local disk storage lives in `paperclip-data`.
Raman thread history and DBOS workflow state live in `raman-state`.
Homi and Vikram keep their thread history and SDK session state in `homi-state` and `vikram-state`.

The first production deploy after Postgres consolidation wrote logical dump backups under `/var/backups/platform/postgres-consolidation/` before restoring into the shared `platform-postgres` container. Legacy Prefect/Airflow Postgres containers were stopped after smoke checks; keep backup/restore decisions tied to explicit maintenance windows.

At minimum, take a DigitalOcean Droplet snapshot before the first public cutover and before database-affecting changes.

## Decommissioning Checklist

- New public endpoints verified.
- DNS has propagated to the new Droplet IP.
- Caddy certificates issued successfully.
- Prefect worker is polling the expected work pool.
- Paperclip health endpoint is reachable after Caddy basic auth.
- Airflow scheduler is running.
- Human approval recorded for each old resource deletion.

Detailed old-resource shutdown steps live in `docs/deprecation-plan.md`.
