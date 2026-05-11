# Secrets

Never commit secret values. Use `.env.local` for local development, `.env.production` on the Droplet, and GitHub Secrets after repo creation.

## Required Names

- `PREFECT_POSTGRES_PASSWORD`: Prefect PostgreSQL password.
- `PLATFORM_POSTGRES_PASSWORD`: Shared production PostgreSQL superuser password for the consolidated Postgres container.
- `PREFECT_BASIC_AUTH_USER`: Caddy username for Prefect UI/API.
- `PREFECT_BASIC_AUTH_HASH`: Caddy-compatible bcrypt password hash.
- `PAPERCLIP_POSTGRES_PASSWORD`: Paperclip PostgreSQL role password.
- `PAPERCLIP_BASIC_AUTH_USER`: Caddy username for Paperclip.
- `PAPERCLIP_BASIC_AUTH_HASH`: Caddy-compatible bcrypt password hash for Paperclip. Use credentials separate from Prefect.
- `PAPERCLIP_BETTER_AUTH_SECRET`: Paperclip Better Auth secret.
- `PAPERCLIP_AGENT_JWT_SECRET`: Paperclip agent JWT signing secret.
- `DO_INFERENCE_API_KEY`: DigitalOcean model access key for Raman when `RAMAN_MODEL_PROVIDER=digitalocean`. Scope the production key to `openai-gpt-oss-120b`.
- `TELEGRAM_BOT_TOKEN`: Raman Telegram bot token from BotFather.
- `TELEGRAM_WEBHOOK_SECRET`: Raman Telegram webhook secret. Generate with `openssl rand -hex 32`.
- `TELEGRAM_ALLOWED_CHAT_IDS`: Comma-separated chat IDs allowed to use the Raman Telegram interface.
- `PUSHOVER_APP_TOKEN`: Prefect daily brief notifications.
- `PUSHOVER_USER_KEY`: Prefect daily brief notifications.
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

Raman production constants are tracked in the deploy workflows, not in secrets:

- `RAMAN_MODEL_PROVIDER=digitalocean`
- `RAMAN_DEV_MODEL=openai-gpt-oss-120b`
- `RAMAN_AGENT=raman`
- `RAMAN_PUBLIC_BASE_URL=https://raman.raniendu.dev`

## Human Login Credentials

Production Caddy basic-auth passwords are intentionally not stored in `.env.production.generated`. That generated file is used for the GitHub `PLATFORM_ENV_FILE` secret and contains Caddy bcrypt hashes such as `PAPERCLIP_BASIC_AUTH_HASH`, plus internal service secrets such as `PAPERCLIP_BETTER_AUTH_SECRET`.

Use `.env.production.credentials` for human-readable production login values:

```bash
grep '^PAPERCLIP_BASIC_AUTH_' .env.production.credentials
```

For the browser prompt at `https://paperclip.raniendu.dev`, use `PAPERCLIP_BASIC_AUTH_USER` and `PAPERCLIP_BASIC_AUTH_PASSWORD` from `.env.production.credentials`. `PAPERCLIP_BETTER_AUTH_SECRET` is not a browser login password; it is an internal Paperclip auth/session secret.

## Optional Provider Keys

- `OPENAI_API_KEY`: Optional Paperclip provider key.
- `ANTHROPIC_API_KEY`: Optional Paperclip provider key.
- `GEMINI_API_KEY`: Optional Paperclip provider key when also configured for Prefect.
- `PARALLEL_API_KEY`: Optional Raman web-search provider key when the active agent spec enables `web_search`.

## Rotation Notes

Rotate app API keys at the provider first, then update `.env.production` and restart only the affected service where possible.

Rotate database passwords during a maintenance window. Production uses one Postgres container with separate `prefect`, `airflow`, and `paperclip` roles/databases, so update the Postgres role password and Compose env file together. Rotate `PLATFORM_POSTGRES_PASSWORD` separately from the app database role passwords.

Rotate Paperclip `PAPERCLIP_BETTER_AUTH_SECRET` and `PAPERCLIP_AGENT_JWT_SECRET` only with an application-level plan for active sessions and agent credentials. Treat Paperclip bootstrap invite URLs as credentials; generate them manually and do not store them in GitHub Actions logs.

Rotate Airflow `FERNET_KEY` using Airflow's documented key rotation process; replacing it blindly can make encrypted connection values unreadable.

Generate Caddy hashes with:

```bash
caddy hash-password --plaintext 'new-password'
```

When a Caddy bcrypt hash is stored in a Compose `--env-file`, escape dollar signs as `$$` so Compose does not treat hash segments as variable interpolation.

## Production Env File

`PLATFORM_ENV_FILE` should contain shared production values such as database passwords, Caddy auth hashes, and app provider keys. Do not include comments with secret values in this secret; keep it as plain `KEY=value` lines. The deploy workflow appends image refs, app deploy flags, and Raman runtime values to the host env file during deployment.
