# Operations

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
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production logs -f airflow-scheduler
```

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
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production pull dotdev prefect-server prefect-worker airflow-init airflow-webserver airflow-scheduler paperclip
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production up --no-build --force-recreate paperclip-db-init
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production up -d --no-build
```

Preferred production redeploy path:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

The GitHub workflow applies Terraform, handles temporary SSH firewall access, pulls SHA-pinned images, recreates Caddy, runs public smoke checks, and cleans up temporary access.

## Temporary SSH Access

Use the `Temporary SSH Access` workflow only when an interactive host session is required and the DigitalOcean web console is unavailable. Pass a single administrator `/32` CIDR, keep the window short, and let the workflow close the rule automatically. Do not use this workflow to add broad CIDRs such as `0.0.0.0/0`.

The `s-1vcpu-2gb` migration is complete. Use `Deploy` for routine releases. Keep `Migrate Smaller Droplet` as the audited pattern for future new-Droplet migrations; do not use local `doctl` for write operations.

## Health Checks

```bash
curl -I https://raniendu.dev/
curl -I https://www.raniendu.dev/
curl -I https://prefect.raniendu.dev/
curl -I https://paperclip.raniendu.dev/
curl -I https://flow.raniendu.dev/
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production ps
```

Prefect API health:

```bash
curl https://prefect.raniendu.dev/api/health
```

Paperclip direct health from the host:

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production exec paperclip curl --fail --header 'Host: paperclip.raniendu.dev' http://localhost:3100/api/health
```

## Paperclip Admin Bootstrap

Generate the first admin invite only in an interactive local or host shell after Paperclip is running:

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production exec paperclip pnpm paperclipai auth bootstrap-ceo --config /etc/paperclip/config.json --base-url https://paperclip.raniendu.dev
```

Treat the invite URL as a credential and do not paste it into GitHub Actions logs, issues, docs, or chat.

## Backups

Back up named volumes before risky deploys:

- `postgres-data`
- `caddy-data`
- `caddy-config`
- `paperclip-data`

Paperclip metadata lives in the `paperclip` database inside `postgres-data`; Paperclip local disk storage lives in `paperclip-data`.

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
