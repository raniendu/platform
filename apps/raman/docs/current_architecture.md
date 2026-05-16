# Current Architecture

Snapshot of what's actually in `main` as of **2026-05-10**. This doc describes
*what exists*; for *where things are headed*, see
[architecture_roadmap.md](architecture_roadmap.md).

All diagrams render natively on GitHub (mermaid). The relational schema also
lives as machine-checked DBML at [`schema.dbml`](schema.dbml) — `pydbml` (dev
dep) parses it; the generated SQL matches `raman/gateway.py::ThreadStore.
_init_schema` 1:1.

## Contents

- [Topology](#topology)
- [Module map](#module-map)
- [Request flows](#request-flows)
  - [Stateless `POST /chat`](#stateless-post-chat)
  - [Threaded `POST /threads/{interface}/{thread}/messages`](#threaded-post-threadsinterfacethreadmessages)
  - [Telegram webhook](#telegram-webhook)
- [Persistence](#persistence)
- [Configuration entry points](#configuration-entry-points)
- [Test entry points](#test-entry-points)

---

## Topology

```mermaid
flowchart LR
    subgraph clients[Clients]
        cli[CLI / curl]
        tg[Telegram]
    end

    subgraph app[FastAPI process - raman.api]
        chat["/chat<br/>stateless"]
        thread["/threads/...<br/>durable"]
        events["/events/{wf_id}"]
        wh["/telegram/{bot}/webhook<br/>/telegram/webhook alias"]
    end

    subgraph runtime[In-process workers]
        dispatch[EventDispatcher]
        inq["INBOUND_QUEUE<br/>concurrency=1"]
        outq["OUTBOUND_QUEUE<br/>concurrency=1"]
        proc[process_inbound_message_event]
        deliver[deliver_reply_event]
    end

    subgraph core[Agent core]
        factory[build_agent]
        spec[("spec/&lt;name&gt;/agent.toml")]
        tools[TOOL_REGISTRY]
        model["OllamaModel<br/>OllamaProvider"]
    end

    subgraph stores[State]
        appdb[("raman.sqlite3<br/>threads + telegram_updates")]
        dbosdb[("dbos.sqlite3<br/>DBOS workflows")]
    end

    cli -->|/chat| chat
    cli -->|/threads| thread
    tg -->|webhook| wh
    chat --> factory
    thread --> dispatch
    wh --> dispatch
    dispatch --> inq
    inq --> proc
    proc --> factory
    proc -->|telegram only| outq
    outq --> deliver
    deliver -->|httpx| tg
    factory --> spec
    factory --> tools
    factory --> model
    proc --> appdb
    inq --> dbosdb
    outq --> dbosdb
    events --> dbosdb
```

The CLI (`uv run raman`) bypasses the HTTP layer entirely. Interactive mode
calls `build_agent` directly and uses Pydantic AI's `to_cli_sync`; one-shot
mode (`--once --prompt ...`) calls the same agent with `run_sync` and exits.

---

## Module map

| Module | Role |
|---|---|
| `raman/cli.py` | `uv run raman` entrypoint. Loads spec, builds agent, then either drops into Pydantic AI's interactive CLI or runs one prompt with `--once`. |
| `raman/api.py` | FastAPI app + lifespan. Routes: `/chat`, `/threads/{interface}/{thread}/messages`, `/events/{workflow_id}`, `/telegram/{bot}/webhook`, legacy `/telegram/webhook`, `/healthz`. Caches one `Agent` per spec in module-level `_agents`. |
| `raman/agent.py` | `build_agent(spec, settings)` — single chokepoint that turns a spec into a `pydantic_ai.Agent[None, str]`. Wires instructions, identity/datetime injectors, and tools. |
| `raman/spec.py` | `AgentSpec` Pydantic model + `load_spec(name, root)`. Reads `agent.toml`, assembles instructions in order: system prompt → shared context → local context. |
| `raman/context.py` | Runtime instruction injectors (`agent_identity`, `current_datetime`). |
| `raman/settings.py` | `RamanSettings` (env-driven) + `build_model`. Currently wires `OllamaModel` against `OLLAMA_BASE_URL`. Single point of model-provider swap. |
| `raman/tools.py` | `TOOL_REGISTRY: dict[str, Callable]`. Today only `web_search` (Parallel API). Specs reference tools by name. |
| `raman/gateway.py` | `ThreadStore` (SQLite per-thread history + Telegram dedupe), `ConversationService` (load history → run agent → persist), CloudEvent helpers used as queue payloads. |
| `raman/dbos_gateway.py` | `EventDispatcher` (enqueue + status), DBOS workflows `process_inbound_message_event` and `deliver_reply_event`, `INBOUND_QUEUE` and `OUTBOUND_QUEUE` (both `concurrency=1`). |
| `raman/telegram.py` | `TelegramAdapter` — webhook parsing + `update_id` dedupe, chat allowlist, `/start /help /reset /agent` commands. Outbound goes through `format_for_telegram` (markdown → MarkdownV2 via `telegramify-markdown`, entity-aware 4096-char chunking) and is sent with `parse_mode="MarkdownV2"`. |

---

## Request flows

### Stateless `POST /chat`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as raman.api
    participant Agent as pydantic_ai.Agent
    participant Model as OllamaModel

    Client->>API: POST /chat {prompt, agent?}
    API->>API: _get_agent(name) — cached per spec
    API->>Agent: agent.run(prompt)
    Agent->>Model: chat completion (no history)
    Model-->>Agent: completion
    Agent-->>API: result.output
    API-->>Client: 200 {agent, output}
```

No DBOS, no SQLite, no message history. The agent is built once per spec and
cached in `raman.api._agents` for the lifetime of the process. Cold starts
hit `load_spec` + `build_model`.

### Threaded `POST /threads/{interface}/{thread}/messages`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as raman.api
    participant Disp as EventDispatcher
    participant InQ as INBOUND_QUEUE
    participant WF as process_inbound_message_event
    participant Store as ThreadStore (SQLite)
    participant Agent as pydantic_ai.Agent

    Client->>API: POST /threads/{iface}/{tid}/messages {prompt, agent?}
    API->>Disp: enqueue_message(InboundMessage)
    Disp->>InQ: enqueue_async(process_inbound_message_event, event)
    InQ-->>Disp: workflow_handle
    Disp-->>API: EnqueuedEvent(workflow_id, "queued")
    API-->>Client: 200 {workflow_id, thread_id, status:"queued"}

    note over InQ,WF: Worker picks up the workflow
    WF->>Store: get_thread(iface, tid)
    Store-->>WF: ThreadRecord (history bytes or None)
    WF->>Agent: agent.run(prompt, message_history=...)
    Agent-->>WF: result
    WF->>Store: set_history(result.all_messages_json())
    WF-->>InQ: {agent, output, thread_id}

    Client->>API: GET /events/{workflow_id}
    API->>Disp: get_event_status(workflow_id)
    Disp-->>API: DBOS workflow status
    API-->>Client: 200 {status, result, error}
```

The handler returns immediately with a workflow id; the actual `agent.run`
happens inside the DBOS workflow. Polling is the read-back path. DBOS
durability means a process crash mid-run reruns the workflow — the LLM call
is *not* idempotent at the cost level.

### Telegram webhook

```mermaid
sequenceDiagram
    autonumber
    participant TG as Telegram
    participant API as /telegram/{bot}/webhook
    participant Adapter as TelegramAdapter
    participant Store as ThreadStore
    participant Disp as EventDispatcher
    participant InQ as INBOUND_QUEUE
    participant WF as process_inbound_message_event
    participant OutQ as OUTBOUND_QUEUE
    participant Deliver as deliver_reply_event

    TG->>API: POST /telegram/{bot}/webhook (X-Telegram-Bot-Api-Secret-Token)
    API->>API: load spec/telegram.toml bot and validate secret header
    API->>Adapter: handle_update(payload)
    Adapter->>Store: claim_telegram_update(bot, update_id)
    alt duplicate
        Store-->>Adapter: false
        Adapter-->>API: {status:"duplicate"}
    else first delivery
        Store-->>Adapter: true
        alt chat not in allowlist
            Adapter->>TG: sendMessage "This bot is private."
            Adapter-->>API: {status:"rejected"}
        else allowed, command (/start /help /reset /agent)
            Adapter->>Store: reset_history / set_agent (as needed)
            Adapter->>TG: sendMessage acknowledgement
            Adapter-->>API: {status:"handled"}
        else allowed, plain text
            Adapter->>Disp: enqueue_message(InboundMessage{interface:"telegram", external_thread_id:str(chat_id)})
            Disp->>InQ: enqueue_async
            Disp-->>Adapter: EnqueuedEvent
            Adapter-->>API: {status:"queued", workflow_id}
        end
    end
    API-->>TG: 200

    note over InQ,WF: Inbound workflow runs (same as the threaded flow above)
    WF->>OutQ: enqueue_async(deliver_reply_event) — only when interface=="telegram"
    OutQ->>Deliver: deliver_reply_event(reply event)
    Deliver->>TG: POST sendMessage with parse_mode="MarkdownV2" (markdown converted, entity-aware chunked at 4096, retries up to 3)
```

The webhook ACKs Telegram synchronously after enqueue. Outbound delivery is
its own workflow so the agent run and the send don't share retry semantics.

---

## Persistence

Two SQLite databases under `.raman/` by default. The application schema is
small and stable; the DBOS schema is owned by the framework.

### Application database — `.raman/raman.sqlite3`

Source of truth: `raman/gateway.py::ThreadStore._init_schema`. Mirrored as
DBML in [`schema.dbml`](schema.dbml).

```mermaid
erDiagram
    threads {
        text interface PK "surface namespace"
        text external_thread_id PK "surface-native id as string"
        text agent_name "selected agent spec"
        blob message_history_json "pydantic_ai result.all_messages_json(); NULL after /reset"
        text created_at "UTC ISO 8601"
        text updated_at "UTC ISO 8601, bumped on every write"
    }

    telegram_updates {
        integer update_id PK "Telegram-assigned id"
        text created_at "UTC ISO 8601 inserted_at"
    }
```

Notes that don't fit in the diagram:

- `threads` uses a composite primary key `(interface, external_thread_id)`.
  No foreign keys; the two tables are independent.
- Writes go through `INSERT ... ON CONFLICT(...) DO UPDATE` on the threads
  table, so a write is always one statement regardless of insert vs update.
- `telegram_updates` uses `INSERT OR IGNORE` for at-most-once webhook
  handling. The table grows unbounded (see `docs/backlog.md`).

### Workflow database — `.raman/dbos.sqlite3`

Owned by DBOS. `EventDispatcher.enqueue_message` returns workflow ids
sourced from this DB; `get_event_status` reads back from it. Override with
`DBOS_SYSTEM_DATABASE_URL` (Postgres URL works) when scaling up. Schema is
intentionally not mirrored here — treat it as opaque framework state.

---

## Configuration entry points

All env vars flow through `raman.settings.RamanSettings`, loaded at process
start (and per-request as a singleton through `_get_settings`). The
authoritative reference is the README configuration table; this section
just calls out the structural seams.

| Surface | Env var(s) | Read by |
|---|---|---|
| Model provider | `RAMAN_DEV_MODEL`, `OLLAMA_BASE_URL` | `settings.build_model` — the *only* spot that names the provider class. Swapping providers (DigitalOcean, OpenAI, Anthropic) is a one-function change here. |
| Agent selection | `RAMAN_AGENT`, `RAMAN_SPEC_ROOT` | CLI default agent + API lifespan preload. |
| Threaded persistence | `RAMAN_DB_PATH` | `ThreadStore.__init__` (path; parents are created). |
| Workflow persistence | `DBOS_SYSTEM_DATABASE_URL` | `configure_dbos`; falls back to `sqlite:///<RAMAN_DB_PATH parent>/dbos.sqlite3`. |
| Telegram | `apps/raman/spec/telegram.toml` plus the env names it references, `RAMAN_PUBLIC_BASE_URL` | `telegram_config`, `TelegramAdapter`, plus the webhook handler in `raman.api`. |
| Tool secrets | `PARALLEL_API_KEY` | `raman.tools._parallel_client` (lazy, raises with a clear error if unset). |

---

## Test entry points

| Suite | Boots DBOS? | Notes |
|---|---|---|
| `tests/test_agent.py`, `test_spec.py`, `test_context.py`, `test_cli.py` | No | Pure unit tests on `build_agent`, spec loading, context injectors, and CLI argument parsing. |
| `tests/test_api.py` | No | `/chat` only. Patches `_get_agent` to bypass model wiring. |
| `tests/test_api_gateway.py` | No | `/threads` and `/events` with a `FakeDispatcher` swapped in via `monkeypatch.setattr(api, "_get_dispatcher", ...)`. The blueprint for any threaded test. |
| `tests/test_gateway.py`, `test_telegram.py` | No | Direct unit tests on `ThreadStore`, `TelegramAdapter`, and the parsing helpers. Use a temp SQLite path and a fake `send_text` callback. |
| `tests/test_evals.py` | No (default) / Yes (gated) | Skipped unless `RAMAN_RUN_EVALS=1`. Live LLM-judge run against Ollama. |

The default `uv run pytest` suite is offline and deterministic — 26 passing,
1 skipped (the eval gate). New tests that touch the threaded surface should
follow the `FakeDispatcher` pattern from `test_api_gateway.py` rather than
booting DBOS in-process.

---

## Where to look next

- Forward-looking design and the four growth axes:
  [architecture_roadmap.md](architecture_roadmap.md)
- Threaded surface — usage, design, troubleshooting:
  [threaded_conversations.md](threaded_conversations.md)
- Adding a tool to `TOOL_REGISTRY`:
  [tools.md](tools.md)
- Telegram local testing + webhook setup runbook:
  [telegram_live_testing.md](telegram_live_testing.md)
- Open work pulled out of code review:
  [backlog.md](backlog.md)
