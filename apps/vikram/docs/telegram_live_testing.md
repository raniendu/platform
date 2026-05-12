# Vikram Telegram Live Testing

Set app-specific Telegram values in `apps/vikram/.env` for direct runs:

```env
VIKRAM_PUBLIC_BASE_URL=https://example.ngrok-free.app
VIKRAM_TELEGRAM_BOT_TOKEN=
VIKRAM_TELEGRAM_WEBHOOK_SECRET=
VIKRAM_TELEGRAM_ALLOWED_CHAT_IDS=123456789
```

Start the API:

```bash
uv run --project apps/vikram vikram-api
```

Register the webhook:

```bash
curl -sS "https://api.telegram.org/bot$VIKRAM_TELEGRAM_BOT_TOKEN/setWebhook" \
  --json '{"url":"'"$VIKRAM_PUBLIC_BASE_URL"'/telegram/webhook","secret_token":"'"$VIKRAM_TELEGRAM_WEBHOOK_SECRET"'"}'
```

Supported commands: `/start`, `/help`, `/reset`, and `/agent <name>`.
