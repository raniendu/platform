# Vikram Architecture

Vikram is the Google ADK sibling of Raman under `apps/vikram/`.

## Runtime

- FastAPI serves `/healthz`, `/chat`, threaded DBOS message endpoints, event polling, and Telegram webhook routes.
- Google ADK `LlmAgent` is built from `spec/vikram/agent.toml`.
- Gemini is the default model family via `VIKRAM_MODEL`; live calls require `GOOGLE_API_KEY`.
- Thread rows store an ADK session reference in the `vikram-state` volume, while ADK `DatabaseSessionService` stores event history in `.vikram/adk_sessions.sqlite3`.

## Local

```bash
uv sync --project apps/vikram --locked
uv run --project apps/vikram --locked pytest apps/vikram/tests -q
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build vikram caddy
curl http://vikram.localhost/healthz
```

`VIKRAM_PARALLEL_API_KEY` or `PARALLEL_API_KEY` enables the `web_search` tool.
