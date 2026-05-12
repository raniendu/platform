# Telegram Live Testing

This runbook covers local HTTP testing, Telegram webhook setup, and debugging
`Bad Request: invalid webhook URL specified`.

## 1. Configure Environment

Copy the example and fill in real values:

```bash
cp .env.example .env
```

Required values:

```bash
RAMAN_DEV_MODEL=gemma4:26b
OLLAMA_BASE_URL=http://localhost:11434/v1

TELEGRAM_BOT_TOKEN=<bot token from BotFather>
TELEGRAM_WEBHOOK_SECRET=<random secret>
TELEGRAM_ALLOWED_CHAT_IDS=<your chat id>
RAMAN_PUBLIC_BASE_URL=https://<public-https-host>
```

Use shell-compatible assignments with no spaces around `=`. For example,
`RAMAN_PUBLIC_BASE_URL = https://...` will not export the value correctly in a
shell.

Generate a valid webhook secret:

```bash
openssl rand -hex 32
```

Telegram only allows `A-Z`, `a-z`, `0-9`, `_`, and `-` in
`TELEGRAM_WEBHOOK_SECRET`.

## 2. Start Local Services

```bash
ollama serve
ollama pull gemma4:26b
uv run raman-api
```

In another terminal:

```bash
curl -sS http://127.0.0.1:8000/healthz
```

Expected:

```json
{"status":"ok"}
```

## 3. Test Threaded HTTP Locally

```bash
curl -sS http://127.0.0.1:8000/threads/manual/test/messages \
  --json '{"prompt":"Say pong in one word","agent":"raman"}'
```

Copy the returned `workflow_id`, then poll:

```bash
curl -sS http://127.0.0.1:8000/events/<workflow_id>
```

## 4. Get Your Telegram Chat ID

Remove any existing webhook before using `getUpdates`:

```bash
curl -sS "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook"
```

Message your bot in Telegram, then run:

```bash
curl -sS "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates" | jq
```

Use `.message.chat.id` as `TELEGRAM_ALLOWED_CHAT_IDS`. Restart `uv run
raman-api` after editing `.env`.

## 5. Expose Localhost Over HTTPS

Telegram webhooks require an HTTPS URL. For local testing, use a tunnel such as:

```bash
ngrok http 8000
```

Set the HTTPS forwarding URL in `.env`:

```bash
RAMAN_PUBLIC_BASE_URL=https://<ngrok-host>
```

Do not include `/telegram/webhook` in `RAMAN_PUBLIC_BASE_URL`; the setup command
adds that path.

## 6. Validate the Webhook URL Before Setting It

If this command prints an empty value, a placeholder, `localhost`, `127.0.0.1`,
or `http://`, Telegram will reject it:

```bash
printf 'Webhook URL: %s/telegram/webhook\n' "$RAMAN_PUBLIC_BASE_URL"
```

Good examples:

```text
https://abc123.ngrok-free.app/telegram/webhook
https://bot.example.com/telegram/webhook
```

Bad examples:

```text
/telegram/webhook
http://localhost:8000/telegram/webhook
https://example.ngrok-free.app/telegram/webhook
https://abc123.ngrok-free.app:8000/telegram/webhook
```

Telegram supports webhook ports `443`, `80`, `88`, and `8443`. Most tunnel
HTTPS URLs work because they use port `443`.

## 7. Set the Telegram Webhook

Use `jq` to build JSON safely:

```bash
set -a
source .env
set +a

curl -sS -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg url "$RAMAN_PUBLIC_BASE_URL/telegram/webhook" \
    --arg secret "$TELEGRAM_WEBHOOK_SECRET" \
    '{url: $url, secret_token: $secret, drop_pending_updates: true}')"
```

Check status:

```bash
curl -sS "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo" | jq
```

The `url` field should match your public HTTPS webhook URL.

## 8. Live Test in Telegram

Send these messages to the bot:

```text
/start
hello
/agent raman
/reset
```

For group chats, add the group chat ID to `TELEGRAM_ALLOWED_CHAT_IDS`. If the bot
does not see group messages, check the bot's privacy mode in BotFather.

## Debugging `invalid webhook URL specified`

This error means Telegram rejected the webhook URL syntax or reachability rules.
Check these first:

1. `RAMAN_PUBLIC_BASE_URL` is set in the shell where you run `curl`.
2. `.env` assignments do not contain spaces around `=`.
3. It starts with `https://`, not `http://`.
4. It is not `localhost`, `127.0.0.1`, or a private LAN address.
5. It is not the placeholder `https://example.ngrok-free.app`.
6. It does not include the webhook path twice.
7. It does not use an unsupported explicit port.

Quick diagnosis:

```bash
echo "$RAMAN_PUBLIC_BASE_URL"
printf '%s\n' "$RAMAN_PUBLIC_BASE_URL/telegram/webhook"
curl -sS "$RAMAN_PUBLIC_BASE_URL/healthz"
```

If `curl -sS "$RAMAN_PUBLIC_BASE_URL/healthz"` does not return
`{"status":"ok"}`, fix the tunnel or public base URL before calling
`setWebhook`.

Reference: Telegram Bot API `setWebhook` requires an HTTPS URL and sends the
secret as `X-Telegram-Bot-Api-Secret-Token`:
https://core.telegram.org/bots/api#setwebhook
