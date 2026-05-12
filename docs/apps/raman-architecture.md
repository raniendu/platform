# Raman Architecture

Raman is the personal agent service under `apps/raman/`. The platform deploy
workflow builds the app image from that directory, provides runtime
environment, persists local state, and routes public traffic through Caddy.

## Runtime

```mermaid
flowchart LR
  caddy["Caddy route<br/>raman.raniendu.dev"]
  raman["raman<br/>FastAPI :8000"]
  state["raman-state volume<br/>/app/.raman"]
  doai["DigitalOcean Inference API"]
  telegram["Telegram Bot API"]
  parallel["Parallel API<br/>optional web_search"]

  caddy --> raman
  raman --> state
  raman --> doai
  raman --> telegram
  raman -. optional .-> parallel
```

The container listens on plain HTTP port `8000`. Production exposes only Caddy
on ports `80` and `443`; Caddy forwards `https://raman.raniendu.dev` to
`raman:8000`.

## State

Raman stores SQLite thread history and DBOS workflow state under `/app/.raman`.
Both local and production Compose mount that path from the `raman-state` named
volume. Losing the volume loses conversation history and in-flight DBOS state,
but does not affect the built image.

## Configuration

Production uses `RAMAN_MODEL_PROVIDER=digitalocean` and
`RAMAN_DEV_MODEL=gemma-4-31B-it`. `RAMAN_DEV_MODEL` is the upstream Raman
setting for the provider-specific model identifier, so in production it names a
DigitalOcean serverless inference model rather than a local development model.
The deploy workflow appends those production constants to the host env file and
validates the DigitalOcean inference key and Telegram secrets from the GitHub
`production` environment when `DEPLOY_RAMAN=true`. `PARALLEL_API_KEY` is
optional unless the active Raman agent spec enables `web_search`.

Local Compose builds `apps/raman` and defaults to `RAMAN_MODEL_PROVIDER=ollama`
and `RAMAN_DEV_MODEL=gemma4:26b`, with
`OLLAMA_BASE_URL` pointing at `host.docker.internal:11434` so a host Ollama
daemon can serve the container.

## Validation

```bash
uv run --project apps/raman pytest apps/raman/tests -q
bash deploy/scripts/prod-app-flags.sh validate deploy/apps.prod.env
bash deploy/scripts/render-prod-caddy.sh deploy/apps.prod.env deploy/caddy/prod-sites
RAMAN_IMAGE=ghcr.io/raniendu/platform/raman:ci docker compose -f deploy/compose/docker-compose.prod.yml --env-file .env.ci config
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local config
```
