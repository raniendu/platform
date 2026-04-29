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
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production logs -f airflow-scheduler
```

## Restarts

Restart one service:

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production restart prefect-worker
```

Pull and restart the current production images:

```bash
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production pull dotdev prefect-server prefect-worker airflow-init airflow-webserver airflow-scheduler
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production up -d --no-build
```

Preferred production redeploy path:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

The GitHub workflow applies Terraform, handles temporary SSH firewall access, pulls SHA-pinned images, recreates Caddy, runs public smoke checks, and cleans up temporary access.

## Health Checks

```bash
curl -I https://raniendu.dev/
curl -I https://www.raniendu.dev/
curl -I https://prefect.raniendu.dev/
curl -I https://flow.raniendu.dev/
docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.production ps
```

Prefect API health:

```bash
curl https://prefect.raniendu.dev/api/health
```

## Backups

Back up named volumes before risky deploys:

- `postgres-data`
- `caddy-data`
- `caddy-config`

The first production deploy after Postgres consolidation writes logical dump backups under `/var/backups/platform/postgres-consolidation/` before restoring into the shared `platform-postgres` container. Keep the legacy `prefect-postgres-data` and `airflow-postgres-data` volumes until the consolidated database has been verified and accepted.

At minimum, take a DigitalOcean Droplet snapshot before the first public cutover and before database-affecting changes.

## Decommissioning Checklist

- New public endpoints verified.
- DNS has propagated to the new Droplet IP.
- Caddy certificates issued successfully.
- Prefect worker is polling the expected work pool.
- Airflow scheduler is running.
- Human approval recorded for each old resource deletion.

Detailed old-resource shutdown steps live in `docs/deprecation-plan.md`.
