# Architecture

## Services

Current production host:

- DigitalOcean Droplet `platform-shared`
- IP `174.138.71.121`
- size `s-1vcpu-2gb`
- weekly Droplet backups enabled

The platform can run five application services behind Caddy:

- DotDev: Flask site built from `apps/dotdev/Dockerfile`, listening on port `8501`.
- Prefect: Prefect API/UI server plus a process worker, built from `apps/prefect/Dockerfile`, listening on port `4200`.
- Paperclip: upstream `paperclipai/paperclip` built from `apps/paperclip/Dockerfile`, listening on port `3100`.
- Raman: in-repo FastAPI/Pydantic AI agent app in `apps/raman`, listening on port `8000`.
- Flow: Apache Airflow API server and scheduler, built from `apps/flow/Dockerfile`, listening on port `8080`.

Production app launch is controlled by tracked flags in `deploy/apps.prod.env`. The current production setting enables DotDev, Prefect, and Raman, and keeps Flow/Airflow and Paperclip disabled without deleting their code, configuration, databases, or Docker volumes.

App-level architecture docs:

- [DotDev](apps/dotdev-architecture.md)
- [Prefect](apps/prefect-architecture.md)
- [Flow / Airflow](apps/flow-architecture.md)
- [Paperclip](apps/paperclip-architecture.md)
- [Raman](apps/raman-architecture.md)

Database and datastore ownership docs:

- [Database documentation](database/README.md)
- [PyDBML-compatible datastore model](database/platform-app-datastores.dbml)

## Container Layout

Local Compose starts:

- `caddy`
- `dotdev`
- `prefect-postgres`
- `prefect-server`
- `prefect-worker`
- `paperclip-postgres`
- `paperclip`
- `raman`
- `airflow-postgres`
- `airflow-init`
- `airflow-webserver`
- `airflow-scheduler`

Production Compose adds durable Caddy certificate volumes and uses one shared Postgres container, `platform-postgres`, with separate `prefect`, `airflow`, and `paperclip` databases and roles. Raman keeps SQLite thread history and DBOS workflow state in the `raman-state` Docker volume. Optional production app services are behind Docker Compose profiles so disabled apps are not started by routine deploys. This lower-memory shape is what allows the smaller `s-1vcpu-2gb` Droplet migration.

## Networking

All services join one Docker network:

- local: `platform-local`
- production: `platform-prod`

Caddy is the only service that needs public ingress. Direct app ports are exposed in local development for smoke tests, but production traffic should enter on ports `80` and `443` only.

## Routing

Local Caddy routes:

- `http://dotdev.localhost` -> `dotdev:8501`
- `http://prefect.localhost` -> `prefect-server:4200`
- `http://raman.localhost` -> `raman:8000`
- `http://paperclip.localhost` -> `paperclip:3100`, protected by Caddy basic auth
- `http://flow.localhost` -> `airflow-webserver:8080`

Production Caddy routes are rendered during deploy from `deploy/apps.prod.env`:

- `https://raniendu.dev` -> DotDev when `DEPLOY_DOTDEV=true`, otherwise `404`
- `https://prefect.raniendu.dev` -> Prefect when `DEPLOY_PREFECT=true`, otherwise `404`
- `https://paperclip.raniendu.dev` -> Paperclip when `DEPLOY_PAPERCLIP=true`, otherwise `404`
- `https://raman.raniendu.dev` -> Raman when `DEPLOY_RAMAN=true`, otherwise `404`
- `https://flow.raniendu.dev` -> Airflow when `DEPLOY_FLOW=true`, otherwise `404`

## Data Volumes

Local volumes:

- `prefect-postgres-data`
- `paperclip-postgres-data`
- `paperclip-data`
- `airflow-postgres-data`
- `airflow-logs`
- `airflow-plugins`
- `raman-state`

Production volumes:

- `caddy-data`
- `caddy-config`
- `postgres-data`
- `paperclip-data`
- `airflow-logs`
- `airflow-plugins`
- `airflow-config`
- `raman-state`

The old separate production Postgres volumes, `prefect-postgres-data` and `airflow-postgres-data`, are not part of the current steady-state stack after the accepted Postgres consolidation and smaller-Droplet migration. Airflow DAGs are mounted from `apps/flow/dags`.
