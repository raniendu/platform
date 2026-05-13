# Threaded Conversations

`POST /chat` is the simple, stateless surface — each request runs the agent
fresh with no message history. The threaded surface
(`POST /threads/{interface}/{thread}/messages`) adds three things on top:

1. **Persistent message history** keyed on `(interface, external_thread_id)`.
2. **Durable execution** via DBOS — if the process restarts mid-run, the
   workflow resumes.
3. **Per-thread serialization** so two messages in the same thread never run
   concurrently against the same history.

This doc explains the moving parts, when to use which surface, and how to
debug the common failure modes.

## When to use which surface

| Use case                                                | Surface                                              |
| ------------------------------------------------------- | ---------------------------------------------------- |
| One-shot question, no follow-up, you'll handle history  | `POST /chat`                                         |
| Multi-turn conversation tied to a user/channel/thread   | `POST /threads/{interface}/{thread}/messages`        |
| Telegram (already wired)                                | `POST /telegram/{bot}/webhook` → threaded, automatic |
| Adding a new chat surface (Slack, Discord, web UI)      | Threaded — model your interface as a new `interface` |

`/chat` is fine for scripting, evals, and HTTP probes. The threaded surface
is the right default for anything user-facing.

## The thread key

Every threaded message identifies its conversation with two strings:

- `interface` — the chat surface (`telegram`, `slack`, `web`, `manual`, etc.)
- `external_thread_id` — the surface's native thread/chat identifier
  (Telegram chat ID as a string, Slack channel ID, your web session ID...)

These are concatenated into `interface:external_thread_id` for logs and
workflow IDs, and used as the composite primary key in the `threads` SQLite
table. Pick `interface` names deliberately — they are the namespace that
keeps a Slack channel `C123` from colliding with a Telegram chat `C123`.

## Architecture

```
client                    FastAPI                 DBOS                       SQLite
------                    -------                 ----                       ------
POST /threads/.../messages
        │
        ▼
   EventDispatcher.enqueue_message
        │  build CloudEvent (raman.message.received)
        ▼
   INBOUND_QUEUE.enqueue_async ────────────────► process_inbound_message_event (workflow)
        │                                                 │
   {workflow_id, "queued"} ──► client                     │  load history, run agent,
                                                          │  persist new history
                                                          ▼
                                                    ConversationService ──► threads table
                                                          │
                                          (telegram only) │ enqueue raman.message.reply_requested
                                                          ▼
                                                  OUTBOUND_QUEUE ──► deliver_reply_event
                                                                              │
                                                                              ▼
                                                                         Telegram sendMessage
```

The handler returns the workflow ID immediately. The actual agent run
happens inside the DBOS workflow. Poll `GET /events/{workflow_id}` for
status and result.

If the inbound workflow fails after the webhook ACK, Telegram cannot surface
that exception directly. For Telegram-originated messages, Raman sends a
generic failure reply before re-raising the workflow error so the DBOS status
and structured logs still show the real failure.

### Modules at a glance

- `raman/api.py` — exposes the HTTP routes.
- `raman/gateway.py`
  - `ThreadStore` — SQLite table + helpers (`get_thread`, `set_history`,
    `set_agent`, `reset_history`, `claim_telegram_update`).
  - `ConversationService.send_message` — load history → run agent → persist.
  - CloudEvent helpers — message envelopes carried through the queues.
- `raman/dbos_gateway.py`
  - `EventDispatcher` — enqueue + status lookup.
  - `INBOUND_QUEUE`, `OUTBOUND_QUEUE` — DBOS queues, both
    `concurrency=1` (see below).
  - `process_inbound_message_event`, `deliver_reply_event` — workflows.
- `raman/telegram.py` — adapts Telegram webhook payloads into
  `InboundMessage` and handles `/start`, `/help`, `/reset`, `/agent`.

## Persistence

Two SQLite databases by default, both under `.raman/`:

- `raman.sqlite3` — application state. Tables:
  - `threads(interface, external_thread_id, agent_name, message_history_json,
    created_at, updated_at)` — primary key on `(interface,
    external_thread_id)`. `message_history_json` is the raw bytes from
    `result.all_messages_json()`.
  - `telegram_updates(update_id, created_at)` — webhook deduplication.
- `dbos.sqlite3` — DBOS workflow + queue state.

Override either with `RAMAN_DB_PATH` and `DBOS_SYSTEM_DATABASE_URL`. To
move DBOS state to Postgres, point `DBOS_SYSTEM_DATABASE_URL` at a
`postgresql://...` URL.

## Concurrency model

Both queues run with `concurrency=1`. This is intentional and load-bearing:

- The inbound workflow does `get_thread → agent.run → set_history` without
  holding a row lock. With more than one worker, two messages in the same
  thread could read the same history concurrently and race on the write,
  losing one turn.
- The outbound queue is serialized too because Telegram rate-limits
  per-bot.

If you need throughput, the right move is to partition by
`hash(interface, external_thread_id) % N` so different threads run in
parallel but a given thread stays serialized — not to bump
`concurrency`. See `docs/backlog.md` for context.

## Inspecting a workflow

```bash
# Enqueue a message:
curl -sS http://127.0.0.1:8000/threads/manual/test/messages \
  --json '{"prompt":"say pong","agent":"raman"}'
# → {"workflow_id":"...","thread_id":"manual:test","status":"queued"}

# Poll status:
curl -sS http://127.0.0.1:8000/events/<workflow_id>
```

Status values come straight from DBOS (`PENDING`, `ENQUEUED`, `SUCCESS`,
`ERROR`, `CANCELLED`, ...). `NOT_FOUND` means DBOS has no record of that
workflow ID — usually a typo.

## Resetting and switching agents

For Telegram (and any surface that wires to the `ThreadStore`):

- `/reset` clears `message_history_json` for the thread but keeps the
  selected agent.
- `/agent <name>` switches the selected agent for the thread. Note that
  prior message history is preserved across the switch — see
  `docs/backlog.md` for the open issue and intended fix.

For programmatic resets, call `ThreadStore.reset_history(interface,
external_thread_id)` directly.

## Adding a new interface

1. Pick an `interface` name that won't collide with anything else.
2. Build an adapter that turns inbound payloads into `InboundMessage` and
   calls `EventDispatcher.enqueue_message`.
3. If you need outbound delivery, add a branch in `deliver_reply_event`
   (or extend it to dispatch by `interface`) and add a step like
   `send_telegram_reply` for the actual send.
4. Add any required env vars to `RamanSettings`, `.env.example`, and the
   README configuration table.

The HTTP `/threads/{interface}/{thread}/messages` route already covers
case (2) for any caller that can issue HTTPS requests — you only need a
custom adapter when the upstream protocol is webhook-shaped (Telegram,
Slack Events API, etc.) or needs delivery back through a third party.

## Troubleshooting

- **Workflow stays `ENQUEUED` forever.** DBOS isn't running. Make sure the
  process was started via `uv run raman-api` (the FastAPI lifespan calls
  `launch_dbos`); if you imported `raman.api.app` from your own server,
  call `launch_dbos(settings)` and `shutdown_dbos()` in your lifespan.
- **`UNIQUE constraint failed: telegram_updates.update_id`.** Telegram
  retried a webhook before you ACK'd. The dedupe path returns `duplicate`
  and skips processing; safe to ignore.
- **Different threads get each other's history.** Check the `interface`
  argument — two surfaces using the same `interface` name with overlapping
  IDs will collide on the composite key.
- **Tests boot DBOS unexpectedly.** Patch `raman.api._get_dispatcher` with
  a fake (see `tests/test_api_gateway.py::FakeDispatcher`) instead of
  letting the lifespan call `launch_dbos`.

## Related docs

- [docs/telegram_live_testing.md](telegram_live_testing.md) — local
  webhook setup and the `invalid webhook URL specified` runbook.
- [docs/architecture_roadmap.md](architecture_roadmap.md) — where this
  surface fits in the four-axis evolution plan.
- [docs/backlog.md](backlog.md) — open issues on the gateway and Telegram
  adapter.
