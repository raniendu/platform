# Homi Architecture

Homi is the Strands SDK sibling of Raman under `apps/homi/`.

## Runtime

- FastAPI serves `/healthz`, `/chat`, threaded DBOS message endpoints, event polling, and Telegram webhook routes.
- Strands `Agent` is built from `spec/homi/agent.toml`.
- Amazon Bedrock is the default model provider via `HOMI_MODEL_ID` and `HOMI_AWS_REGION`.
- Thread history stores Strands `agent.messages` JSON in the `homi-state` volume.

## Local

```bash
uv sync --project apps/homi --locked
uv run --project apps/homi --locked pytest apps/homi/tests -q
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build homi caddy
curl http://homi.localhost/healthz
```

Live `/chat` calls require AWS Bedrock credentials. `HOMI_PARALLEL_API_KEY` or
`PARALLEL_API_KEY` enables the `web_search` tool.
