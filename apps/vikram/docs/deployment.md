# Vikram Deployment

Vikram is built from `apps/vikram/Dockerfile` and runs on port `8000` inside
the container.

## Local Compose

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build vikram caddy
curl http://vikram.localhost/healthz
```

Local Compose maps host port `8002` to the container, so direct access is also:

```bash
curl http://localhost:8002/healthz
```

## Production

Production wiring is present but disabled by default with
`DEPLOY_VIKRAM=false` in `deploy/apps.prod.env`.

When enabling Vikram, configure DNS for `vikram.raniendu.dev`, set the Vikram
Telegram secrets in the GitHub production environment, and provide
`GOOGLE_API_KEY` for Gemini calls.
