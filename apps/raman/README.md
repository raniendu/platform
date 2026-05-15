# raman

A personal CLI + HTTP agent built on Pydantic AI.

Single-user project — scoped to my own workflows, not for general distribution.

## Stack

- Python 3.13+
- Pydantic AI for the agent runtime
- FastAPI + uvicorn for the HTTP surface
- Pydantic Settings for typed env configuration
- TOML-based agent specs under `spec/`
- pydantic-evals for LLM-judge evaluations
- uv for dependency and virtualenv management
- black + isort enforced via pre-commit

## Project Layout

```text
raman/
├── raman/
│   ├── __init__.py
│   ├── agent.py         # build_agent() factory (loads spec, builds Pydantic AI Agent)
│   ├── api.py           # FastAPI app: /chat, /threads, /events, /telegram, /healthz
│   ├── cli.py           # `uv run raman` entrypoint
│   ├── context.py       # runtime context injectors (identity, current datetime)
│   ├── settings.py      # RamanSettings — env-driven config
│   ├── spec.py          # AgentSpec model + load_spec()
│   ├── tools.py         # TOOL_REGISTRY — name → async callable map
│   ├── gateway.py       # ThreadStore (SQLite) + ConversationService + CloudEvent helpers
│   ├── dbos_gateway.py  # DBOS workflows + queues for threaded message processing
│   └── telegram.py      # TelegramAdapter — webhook parse, allowlist, commands, send
├── spec/
│   ├── raman/
│   │   ├── agent.toml         # spec — name, description, prompt + context pointers
│   │   └── system_prompt.md
│   └── shared/                # (optional) cross-agent context + skills
├── evals/             # pydantic-evals dataset + standalone runner
├── tests/
├── docs/              # architecture roadmap, runbooks, topical guides
├── .env.example
└── pyproject.toml
```

For the current state of the system (modules, request flows, schema), see
[docs/current_architecture.md](docs/current_architecture.md). For where it's
going, see [docs/architecture_roadmap.md](docs/architecture_roadmap.md). For
the Docker image contract and how production composes it, see
[docs/deployment.md](docs/deployment.md).

## Setup

Run these commands from `apps/raman/` when working on Raman directly:

```bash
uv sync
uv run pre-commit install
cp .env.example .env

ollama pull gemma4:26b
ollama serve
```

The direct app `.env` is separate from the platform root `.env.local`. Use:

```env
OLLAMA_BASE_URL=http://localhost:11434/v1
```

for direct `uv` runs. The platform Docker Compose stack uses root `.env.local`
with:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
```

because the Raman container reaches Ollama through Docker Desktop's host
bridge.

For the migrated platform workflow, the common root commands are:

```bash
uv sync --project apps/raman --locked
uv run --project apps/raman --locked pytest apps/raman/tests -q
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build raman
curl http://localhost:8000/healthz
```

## CLI

```bash
uv run raman                  # interactive chat with the default agent (raman)
uv run raman --agent alfred   # any agent under spec/<name>/
```

The CLI prompt label reflects the active agent's spec name.

## HTTP API

```bash
uv run raman-api              # serves on http://127.0.0.1:8000
```

Then, from another terminal:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/chat --json '{"prompt":"say pong"}'
```

Endpoints:

| Method | Path        | Body                                       | Description                |
| ------ | ----------- | ------------------------------------------ | -------------------------- |
| POST   | `/chat`     | `{"prompt": "...", "agent"?: "<name>"}`    | Single-shot agent run      |
| GET    | `/healthz`  | —                                          | Liveness check             |
| GET    | `/docs`     | —                                          | Swagger UI (FastAPI auto)  |
| POST   | `/threads/{interface}/{thread}/messages` | `{"prompt": "...", "agent"?: "<name>"}` | Enqueue a persistent threaded run |
| GET    | `/events/{workflow_id}` | — | Inspect a DBOS workflow result |

```bash
curl -sS http://127.0.0.1:8000/chat \
     --json '{"prompt": "what is your name?"}'
# → {"agent":"raman","output":"Your name is raman."}
```

`POST /chat` is stateless — each request runs the agent fresh, no
server-side message history. The default agent (`RAMAN_AGENT`, default
`raman`) is pre-loaded at startup; other specs are built lazily on first use.

`POST /threads/{interface}/{thread}/messages` enqueues a DBOS workflow that
loads prior history for `(interface, thread)` from local SQLite, runs the
agent, and persists the new history. Poll `GET /events/{workflow_id}` for the
result. Default storage lives under `.raman/`; override with `RAMAN_DB_PATH`
and `DBOS_SYSTEM_DATABASE_URL`. Full design and operational notes:
[docs/threaded_conversations.md](docs/threaded_conversations.md).

## Logging

Raman writes structured JSON logs to stdout. The app does not create a local log
file or ship logs to an external backend.

- Direct `uv run raman-api`: logs are in the terminal running the API.
- Local Compose: `docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f raman`.
- Production Compose: logs are Docker container stdout on the Droplet and can be
  inspected with `docker compose ... logs raman` over SSH.

Set `RAMAN_LOG_LEVEL=DEBUG` to include debug-level events. The structured logs
hash chat/thread IDs and avoid raw prompt text, replies, tokens, and webhook
secrets.

## Tracing

Raman can export OpenTelemetry traces through OpenLIT. Tracing is off by default
and should be enabled explicitly:

```bash
RAMAN_OBSERVABILITY_ENABLED=true
RAMAN_OTLP_ENDPOINT=http://jaeger:4318
```

Local platform Compose includes Jaeger v2 at `http://localhost:16686`.
Production Compose includes a gated `observability` profile. When
`DEPLOY_OBSERVABILITY=true`, the deploy workflow enables Raman tracing and sends
production traces to `http://jaeger:4318`; the Jaeger UI is exposed at
`https://jaeger.raniendu.dev` behind Caddy basic auth. Message-content capture
is off by default and is forced off in production even if
`RAMAN_OBSERVABILITY_CAPTURE_MESSAGE_CONTENT=true` is set. Raman disables the
OpenLIT `mistral` instrumentor by default because this app does not use that SDK
and the installed package can produce noisy startup instrumentation failures.

## Telegram

Telegram is wired as another interface through the FastAPI app:

```bash
uv run raman-api
uv run python -m raman.local_webhook "$RAMAN_PUBLIC_BASE_URL" --bot raman
```

Telegram bots are configured in `spec/telegram.toml`. Each `[[bots]]` entry
binds a bot name to a default agent spec and names the env vars that hold its
BotFather token, webhook secret, allowed chat IDs, and optional bot username.
Private and group chat IDs are supported; unknown chats are rejected.
The checked-in config includes `raman`, `gobind`, and `leo`; each uses the same
FastAPI service and named webhook path such as `/telegram/gobind/webhook` or
`/telegram/leo/webhook`.

Private chats respond to every text message. Group and supergroup chats stay
quiet unless the message mentions `@<bot username>`, replies to one of the
bot's messages, or invokes a command for the bot. Raman strips `@<bot username>`
from the prompt before sending it to the model, prefixes group prompts with the
sender display name, and replies with Telegram `reply_to_message_id` so the
answer is attached to the triggering group message. Group history is shared by
chat ID; sender names are context for the model, not separate private memory.

V1 accepts text only and supports `/start`, `/help`, `/reset`, and
`/agent <name>`. In groups, `/reset` and `/agent` require the sender to be a
Telegram chat admin; admin status is verified with Telegram `getChatMember`.
The `/agent` command can switch to any valid `spec/<name>/agent.toml` within
that bot chat, while each bot keeps separate thread history. Replies are
converted from markdown to Telegram MarkdownV2 via `telegramify-markdown` so
bold, code, and bullets render natively. If the asynchronous DBOS workflow
fails after Telegram has already
received the webhook ACK, Raman sends a generic failure reply and keeps the
stack trace in structured logs. See `docs/telegram_live_testing.md` for the full
local live-testing and webhook troubleshooting runbook.

### Local Production-Model Telegram Debugging

Use this when you want the local Raman process to call the same DigitalOcean
serverless inference endpoint as production, while Telegram sends webhooks to
your Mac through ngrok.

From the platform repo root, start Raman locally with the production model
provider:

```bash
./apps/raman/scripts/run-local-prod-debug.sh
```

The script reads root `.env.local` by default, requires `DO_INFERENCE_API_KEY`,
forces `RAMAN_MODEL_PROVIDER=digitalocean`, defaults
`RAMAN_DEV_MODEL=gemma-4-31B-it`, sets `RAMAN_LOG_LEVEL=DEBUG`, and stores local
debug state under `apps/raman/.raman/prod-debug/`.

In another terminal:

```bash
ngrok http 8000
```

Then point Telegram at the ngrok HTTPS URL:

```bash
./apps/raman/scripts/set-local-telegram-webhook.sh https://<ngrok-host>
```

The webhook script validates the URL, checks `<ngrok-url>/healthz`, and calls
Telegram `setWebhook` using the selected bot config from `spec/telegram.toml`
and the referenced env vars from `.env.local`. Use `--bot <name>` for one bot
or `--all` for every configured bot. Override the model with
`RAMAN_LOCAL_DEBUG_MODEL=<model-id>` before running the debug script.

## Defining Agents

Each agent lives in its own folder under `spec/`:

```text
spec/<name>/
├── agent.toml          # the spec — pointers, no prompt body
├── system_prompt.md    # the persona prompt
├── context/            # (optional) local context files
└── skills/             # (optional, placeholder for now)
spec/shared/
├── context/            # (optional) cross-agent context files
└── skills/             # (optional, placeholder)
```

Built-in specs include `raman` for the default personal assistant and `gobind`
for shared Telegram group chats. In a group, a Telegram chat admin can switch
the shared thread with `/agent gobind`.

`spec/raman/agent.toml`:

```toml
name = "raman"
description = "Personal assistant agent for Raniendu."
system_prompt = "system_prompt.md"

# Local resources — relative to spec/<name>/
context_files = []
skills = []

# Shared resources — relative to spec/shared/
shared_context_files = []
shared_skills = []

# Tools — names resolved from raman.tools.TOOL_REGISTRY
tools = ["web_search"]

# Model knobs — passed through to pydantic_ai ModelSettings.
[model_settings]
temperature = 0.3
```

See `spec/raman/agent.toml` for the full annotated list of supported
`model_settings` knobs.

The instructions sent to the model are assembled in this order:
`system_prompt` → shared context files → local context files → injected
runtime context (identity + datetime).

## Context Injection

Every agent run gets two extra instructions appended automatically (see
`raman/context.py`):

- `Your name is <spec.name>.`
- `Current date and time: <ISO 8601> (<tz>).`

Identity flows from `spec.name` so renaming an agent in its spec renames it
everywhere — no hardcoded names in the prompt.

## Configuration

Environment variables (see `.env.example`):

| Variable                      | Default                                | Purpose                                                                    |
| ----------------------------- | -------------------------------------- | -------------------------------------------------------------------------- |
| `RAMAN_DEV_MODEL`             | `gemma4:26b`                           | Ollama model name                                                          |
| `OLLAMA_BASE_URL`             | `http://localhost:11434/v1`            | Ollama server URL                                                          |
| `RAMAN_AGENT`                 | `raman`                                | Default agent spec to load                                                 |
| `RAMAN_SPEC_ROOT`             | `<repo>/spec`                          | Spec folder location                                                       |
| `RAMAN_LOG_LEVEL`             | `INFO`                                 | Structured JSON log level for API, Telegram, DBOS, and agent handoffs      |
| `RAMAN_OBSERVABILITY_ENABLED` | `false`                                | Enable OpenLIT/OpenTelemetry tracing                                       |
| `RAMAN_OTLP_ENDPOINT`         | —                                      | OTLP endpoint, e.g. `http://jaeger:4318` in Compose                         |
| `RAMAN_OBSERVABILITY_CAPTURE_MESSAGE_CONTENT` | `false`                    | Capture prompt/reply content in traces. Forced off in production            |
| `RAMAN_OBSERVABILITY_DISABLED_INSTRUMENTORS` | `mistral`                 | Comma-separated OpenLIT instrumentors to skip                               |
| `RAMAN_DB_PATH`               | `<repo>/.raman/raman.sqlite3`          | SQLite path for the threaded conversation store                            |
| `DBOS_SYSTEM_DATABASE_URL`    | `sqlite:///<repo>/.raman/dbos.sqlite3` | DBOS workflow state DB. Override to use Postgres                           |
| `RAMAN_PUBLIC_BASE_URL`       | —                                      | HTTPS base URL used when registering the Telegram webhook                  |
| `PARALLEL_API_KEY`            | —                                      | Required if any agent spec lists `web_search` in `tools`                   |
| `TELEGRAM_BOT_TOKEN`          | —                                      | BotFather token for the default `spec/telegram.toml` bot                   |
| `TELEGRAM_WEBHOOK_SECRET`     | —                                      | Secret for the default Telegram bot webhook header                         |
| `TELEGRAM_ALLOWED_CHAT_IDS`   | empty                                  | Chat IDs for the default Telegram bot                                      |
| `TELEGRAM_BOT_USERNAME`       | —                                      | Bot username, without `@`; required for group mentions and reply detection |
| `TELEGRAM_API_BASE_URL`       | `https://api.telegram.org`             | Telegram API host for the default bot                                      |
| `GOBIND_TELEGRAM_BOT_TOKEN`   | —                                      | BotFather token for the Gobind Telegram bot                                |
| `GOBIND_TELEGRAM_WEBHOOK_SECRET` | —                                   | Secret for the Gobind Telegram webhook header                              |
| `GOBIND_TELEGRAM_ALLOWED_CHAT_IDS` | empty                              | Chat IDs allowed to use Gobind                                             |
| `GOBIND_TELEGRAM_BOT_USERNAME` | —                                     | Gobind bot username, without `@`; required for group mentions and replies  |
| `GOBIND_TELEGRAM_API_BASE_URL` | `https://api.telegram.org`            | Telegram API host for Gobind                                               |
| `LEO_TELEGRAM_BOT_TOKEN`      | —                                      | BotFather token for the Leo Telegram bot                                   |
| `LEO_TELEGRAM_WEBHOOK_SECRET` | —                                      | Secret for the Leo Telegram webhook header                                 |
| `LEO_TELEGRAM_ALLOWED_CHAT_IDS` | empty                                | Chat IDs allowed to use Leo                                                |
| `LEO_TELEGRAM_BOT_USERNAME`   | —                                      | Leo bot username, without `@`; required for group mentions and replies     |
| `LEO_TELEGRAM_API_BASE_URL`   | `https://api.telegram.org`             | Telegram API host for Leo                                                  |
| `RAMAN_RUN_EVALS`             | unset                                  | Set to `1` to enable live LLM-judge evals in `pytest`                      |

## Adding Tools

Tools are async functions registered in `raman.tools.TOOL_REGISTRY` and
referenced by name from each agent's `agent.toml`. Adding one is two edits:

```python
# raman/tools.py
async def get_weather(city: str) -> str:
    """Return current weather for a city."""
    return f"The weather in {city} is sunny."


TOOL_REGISTRY: dict[str, Callable[..., Awaitable[str]]] = {
    "web_search": web_search,
    "get_weather": get_weather,
}
```

```toml
# spec/raman/agent.toml
tools = ["web_search", "get_weather"]
```

The docstring becomes the tool description shown to the model. Tools needing
secrets read them from `RamanSettings`; see `web_search` for the lazy-client
pattern. Full guide: [docs/tools.md](docs/tools.md).

## Tests and Evals

```bash
uv run pytest                                          # offline unit tests
RAMAN_RUN_EVALS=1 uv run pytest tests/test_evals.py    # live LLM-judge evals (needs Ollama)
uv run python -m evals.run                             # standalone eval runner with full report
```

The default `pytest` suite is offline. Live evals are gated behind
`RAMAN_RUN_EVALS=1` so CI stays clean.

## Formatting

```bash
uv run pre-commit run --all-files
```
