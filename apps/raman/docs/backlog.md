# Backlog

Open work pulled out of code review. Each item names the file/line, the
problem, and a suggested fix. Add to the top as new items come up; move
shipped items to the bottom of their section under a `## Done` heading or
delete once they're committed and tested.

---

## Telegram + gateway

### `/agent <name>` keeps the prior agent's history

`TelegramAdapter._handle_command` (`raman/telegram.py:107-118`) switches the
thread's selected agent via `ThreadStore.set_agent`, which preserves the
prior `message_history_json` (`raman/gateway.py:161-190`). The new
specialist then runs against tool-call traces that may reference tools it
doesn't have, which can produce confused output or validation errors.

**Fix:** reset `message_history_json` to `NULL` inside `set_agent` (or in
the `/agent` command path), and update `/help` to mention that switching
agents starts a fresh conversation.

### `INBOUND_QUEUE` concurrency=1 is load-bearing and undocumented

`raman/dbos_gateway.py:21` caps inbound processing at one worker. The cap
is intentional — concurrent workers on the same `(interface, thread_id)`
would race on `get_thread` → `agent.run` → `set_history`. There is no
comment at the declaration site, and the natural instinct on "make it
faster" is to bump the number.

**Fix (small):** add a one-line comment at the queue declaration. **Fix
(real, only if needed):** partition by `hash(interface, thread_id) %
N_workers` so different threads can run in parallel.

### `telegram_updates` dedupe table grows unbounded

`ThreadStore.claim_telegram_update` (`raman/gateway.py:203-212`) inserts
every webhook `update_id` and never deletes. Personal scale means this
won't matter for years, but it's a permanent leak.

**Fix:** when we add a DBOS scheduled workflow (see Axis 2 in
`architecture_roadmap.md`), include a daily `DELETE FROM telegram_updates
WHERE created_at < ?`. Cheaper alternative: opportunistic delete inside
the same write.

### `send_telegram_reply` rebuilds a full `TelegramAdapter` per outbound message

`raman/dbos_gateway.py:115-123` constructs a `TelegramAdapter` with an
unused `ThreadStore` and `enqueue_message=None` on every delivery, just to
reach `send_message`. The adapter's only sending state is the httpx call.

**Fix:** extract `send_message` and `split_telegram_message` to module-
level functions taking `(settings, chat_id, text)`. Have
`TelegramAdapter.send_message` delegate. The DBOS step calls the function
directly.
