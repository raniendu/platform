# Secrets

Never commit secret values. Use `.env.local` for local development, `.env.production` on the Droplet, and GitHub Secrets after repo creation.

## Required Names

- `PREFECT_POSTGRES_PASSWORD`: Prefect PostgreSQL password.
- `PLATFORM_POSTGRES_PASSWORD`: Shared production PostgreSQL superuser password for the consolidated Postgres container.
- `PREFECT_BASIC_AUTH_USER`: Caddy username for Prefect UI/API and the Jaeger UI when `DEPLOY_OBSERVABILITY=true`.
- `PREFECT_BASIC_AUTH_HASH`: Caddy-compatible bcrypt password hash for Prefect and the Jaeger UI when `DEPLOY_OBSERVABILITY=true`.
- `DO_INFERENCE_API_KEY`: DigitalOcean model access key for Raman when `RAMAN_MODEL_PROVIDER=digitalocean`. Scope the production key to `gemma-4-31B-it`.
- `TELEGRAM_BOT_TOKEN`: Raman default Telegram bot token from BotFather; this env name is referenced by `apps/raman/spec/telegram.toml`.
- `TELEGRAM_WEBHOOK_SECRET`: Raman default Telegram webhook secret. Generate with `openssl rand -hex 32`.
- `TELEGRAM_ALLOWED_CHAT_IDS`: Comma-separated chat IDs allowed to use the default Raman Telegram bot.
- `TELEGRAM_BOT_USERNAME`: Raman default Telegram bot username without `@`; required for group mentions and reply-to-bot detection.
- `GOBIND_TELEGRAM_BOT_TOKEN`: Gobind Telegram bot token from BotFather; this env name is referenced by `apps/raman/spec/telegram.toml`.
- `GOBIND_TELEGRAM_WEBHOOK_SECRET`: Gobind Telegram webhook secret. Generate with `openssl rand -hex 32`.
- `GOBIND_TELEGRAM_ALLOWED_CHAT_IDS`: Comma-separated chat IDs allowed to use the Gobind Telegram bot.
- `GOBIND_TELEGRAM_BOT_USERNAME`: Gobind Telegram bot username without `@`; required for group mentions and reply-to-bot detection.
- `LEO_TELEGRAM_BOT_TOKEN`: Leo Telegram bot token from BotFather; this env name is referenced by `apps/raman/spec/telegram.toml`.
- `LEO_TELEGRAM_WEBHOOK_SECRET`: Leo Telegram webhook secret. Generate with `openssl rand -hex 32`.
- `LEO_TELEGRAM_ALLOWED_CHAT_IDS`: Comma-separated chat IDs allowed to use the Leo Telegram bot.
- `LEO_TELEGRAM_BOT_USERNAME`: Leo Telegram bot username without `@`; required for group mentions and reply-to-bot detection.
- `PARALLEL_API_KEY`: Raman web-search provider key. Required because the current `spec/raman` enables `web_search`.
- `PUSHOVER_APP_TOKEN`: Prefect daily brief notifications. During Prefect deployment this is validated and saved as the Prefect Secret block `pushover-app-token`.
- `PUSHOVER_USER_KEY`: Prefect daily brief notifications. During Prefect deployment this is validated and saved as the Prefect Secret block `pushover-user-key`.
- `GEMINI_API_KEY`: Prefect daily brief rewrite support.
- `AIRFLOW_POSTGRES_PASSWORD`: Airflow PostgreSQL password.
- `AIRFLOW__CORE__FERNET_KEY`: Airflow secret for encrypted values.
- `AIRFLOW__WEBSERVER__SECRET_KEY`: Airflow webserver/session secret.
- `AIRFLOW_ADMIN_USER`: Airflow admin username.
- `AIRFLOW_ADMIN_PASSWORD`: Airflow admin password.
- `ACME_EMAIL`: Caddy ACME registration email.
- `DIGITALOCEAN_ACCESS_TOKEN`: Terraform provider token. The GitHub deploy workflow also uses it to inspect DigitalOcean resources and add/remove the temporary SSH firewall rule. The smaller-Droplet migration workflow uses the same token for its reviewed GitHub Actions-only DigitalOcean writes.
- `DO_SSH_KEY_FINGERPRINTS`: GitHub environment variable or secret containing a Terraform list of SSH key fingerprints allowed on the Droplet, for example `["aa:bb:cc"]`.
- `ALLOWED_SSH_CIDRS`: GitHub environment variable or secret containing a Terraform list of stable SSH source CIDRs for the Droplet firewall, for example `["203.0.113.10/32"]` or `[]`.
- `PLATFORM_SSH_USER`: SSH user for deploy, usually `root` for the initial Droplet.
- `PLATFORM_SSH_PORT`: SSH port for deploy, usually `22`.
- `PLATFORM_SSH_PRIVATE_KEY`: Private key authorized on the Droplet for deployment.
- `PLATFORM_ENV_FILE`: Complete production environment file content for `/opt/platform/.env.production`.

`PLATFORM_SSH_HOST` and `PLATFORM_FIREWALL_ID` are no longer required. The deploy workflow reads the Droplet IP and firewall ID from Terraform outputs. The smaller-Droplet migration workflow discovers both the canonical and staged Droplet IPs from DigitalOcean inventory.

DigitalOcean write access should be used by GitHub Actions workflows only. Local `doctl` is for read-only inventory and verification.

Agent production constants are tracked in the deploy workflows, not in secrets:

- `RAMAN_MODEL_PROVIDER=digitalocean`
- `RAMAN_DEV_MODEL=gemma-4-31B-it`
- `RAMAN_AGENT=raman`
- `RAMAN_PUBLIC_BASE_URL=https://raman.raniendu.dev`

## Human Login Credentials

Production Caddy basic-auth passwords are intentionally not stored in `.env.production.generated`. That generated file is used for the GitHub `PLATFORM_ENV_FILE` secret and contains Caddy bcrypt hashes such as `PREFECT_BASIC_AUTH_HASH`.

Use `.env.production.credentials` for human-readable production login values:

```bash
grep '^PREFECT_BASIC_AUTH_' .env.production.credentials
```

For `https://prefect.raniendu.dev` and `https://jaeger.raniendu.dev`, use the Prefect basic-auth credentials.

## Optional Provider Keys

- `PARALLEL_API_KEY`: Shared web-search provider key for Raman. Required for Raman's current production spec.

## Rotation Notes

Rotate app API keys at the provider first, then update `.env.production` and restart only the affected service where possible.

For Prefect Pushover credentials, redeploy Prefect after updating `PUSHOVER_APP_TOKEN` or `PUSHOVER_USER_KEY`. The deploy workflow refreshes the `pushover-app-token` and `pushover-user-key` Prefect Secret blocks from the production env file before registering flow deployments. The daily brief reads those blocks first and falls back to env vars only if blocks are missing during rollout or local development.

Rotate database passwords during a maintenance window. Production uses one Postgres container with separate `prefect` and `airflow` roles/databases, so update the Postgres role password and Compose env file together. Rotate `PLATFORM_POSTGRES_PASSWORD` separately from the app database role passwords.

Rotate Airflow `FERNET_KEY` using Airflow's documented key rotation process; replacing it blindly can make encrypted connection values unreadable.

Generate Caddy hashes with:

```bash
caddy hash-password --plaintext 'new-password'
```

When a Caddy bcrypt hash is stored in a Compose `--env-file`, escape dollar signs as `$$` so Compose does not treat hash segments as variable interpolation.

## Production Env File

`PLATFORM_ENV_FILE` should contain shared production values such as database passwords, Caddy auth hashes, app provider keys, and Raman Telegram bot keys referenced by `apps/raman/spec/telegram.toml`. Do not include comments with secret values in this secret; keep it as plain `KEY=value` lines. The deploy workflow appends image refs, app deploy flags, and agent runtime values to the host env file during deployment, and writes Raman Telegram entries to `/opt/platform/.env.raman` for the Raman container.
