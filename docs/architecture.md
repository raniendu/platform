# Architecture

## Services

The platform runs three application services behind Caddy:

- DotDev: Flask site built from `apps/dotdev/Dockerfile`, listening on port `8501`.
- Prefect: Prefect API/UI server plus a process worker, built from `apps/prefect/Dockerfile`, listening on port `4200`.
- Flow: Apache Airflow API server and scheduler, built from `apps/flow/Dockerfile`, listening on port `8080`.

## Container Layout

Local Compose starts:

- `caddy`
- `dotdev`
- `prefect-postgres`
- `prefect-server`
- `prefect-worker`
- `airflow-postgres`
- `airflow-init`
- `airflow-webserver`
- `airflow-scheduler`

Production Compose keeps the same shape and adds durable Caddy certificate volumes. Prefect and Airflow each use separate PostgreSQL containers and volumes to avoid cross-service database coupling.

## Networking

All services join one Docker network:

- local: `platform-local`
- production: `platform-prod`

Caddy is the only service that needs public ingress. Direct app ports are exposed in local development for smoke tests, but production traffic should enter on ports `80` and `443` only.

## Routing

Local Caddy routes:

- `http://dotdev.localhost` -> `dotdev:8501`
- `http://prefect.localhost` -> `prefect-server:4200`
- `http://flow.localhost` -> `airflow-webserver:8080`

Production Caddy routes:

- `https://raniendu.dev` -> DotDev
- `https://prefect.raniendu.dev` -> Prefect, protected by Caddy basic auth
- `https://flow.raniendu.dev` -> Airflow

## Data Volumes

Local volumes:

- `prefect-postgres-data`
- `airflow-postgres-data`
- `airflow-logs`
- `airflow-plugins`

Production volumes:

- `caddy-data`
- `caddy-config`
- `prefect-postgres-data`
- `airflow-postgres-data`
- `airflow-logs`
- `airflow-plugins`
- `airflow-config`

Historical Prefect runs and blocks are not migrated. Airflow DAGs are mounted from `apps/flow/dags`.

