# Homi Threaded Conversations

Threaded conversations use the same HTTP contract as Raman:

```bash
curl http://127.0.0.1:8000/threads/web/demo/messages \
  --json '{"prompt":"remember that my project is Homi"}'
curl http://127.0.0.1:8000/events/<workflow_id>
```

`ThreadStore` keys rows by `(interface, external_thread_id)`. The
`message_history_json` column stores Strands `agent.messages` JSON bytes. On
the next turn, Homi rebuilds a Strands agent with those messages before
invoking the new prompt.

Telegram `/reset` sets `message_history_json` to `NULL`, so the next message
starts a fresh Strands conversation.
