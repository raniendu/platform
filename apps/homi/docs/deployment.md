# Homi Deployment

Homi is built from `apps/homi/Dockerfile` and runs on port `8000` inside the
container.

## Local Compose

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build homi caddy
curl http://homi.localhost/healthz
```

Local Compose maps host port `8001` to the container, so direct access is also:

```bash
curl http://localhost:8001/healthz
```

## Production

Production wiring is present but disabled by default with `DEPLOY_HOMI=false`
in `deploy/apps.prod.env`.

When enabling Homi, configure DNS for `homi.raniendu.dev`, set the Homi
Telegram secrets in the GitHub production environment, and provide Bedrock
credentials through either `AWS_BEARER_TOKEN_BEDROCK` or the standard
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` pair.
