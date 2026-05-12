# Vikram Threaded Conversations

Threaded conversations use the same HTTP contract as Raman:

```bash
curl http://127.0.0.1:8000/threads/web/demo/messages \
  --json '{"prompt":"remember that my project is Vikram"}'
curl http://127.0.0.1:8000/events/<workflow_id>
```

`ThreadStore` keys rows by `(interface, external_thread_id)`. The
`message_history_json` column stores the active ADK `session_id` and `user_id`
as JSON bytes. ADK's `DatabaseSessionService` stores the actual event history
in `.vikram/adk_sessions.sqlite3`.

Telegram `/reset` sets `message_history_json` to `NULL`, so the next message
creates a fresh ADK session and no longer uses the old session history.
