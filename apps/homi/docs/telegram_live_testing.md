# Homi Telegram Live Testing

Set app-specific Telegram values in `apps/homi/.env` for direct runs:

```env
HOMI_PUBLIC_BASE_URL=https://example.ngrok-free.app
HOMI_TELEGRAM_BOT_TOKEN=
HOMI_TELEGRAM_WEBHOOK_SECRET=
HOMI_TELEGRAM_ALLOWED_CHAT_IDS=123456789
```

Start the API:

```bash
uv run --project apps/homi homi-api
```

Register the webhook:

```bash
curl -sS "https://api.telegram.org/bot$HOMI_TELEGRAM_BOT_TOKEN/setWebhook" \
  --json '{"url":"'"$HOMI_PUBLIC_BASE_URL"'/telegram/webhook","secret_token":"'"$HOMI_TELEGRAM_WEBHOOK_SECRET"'"}'
```

Supported commands: `/start`, `/help`, `/reset`, and `/agent <name>`.
