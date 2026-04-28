# Secrets

Never commit secret values. Use `.env.local` for local development, `.env.production` on the Droplet, and GitHub Secrets after repo creation.

## Required Names

- `PREFECT_POSTGRES_PASSWORD`: Prefect PostgreSQL password.
- `PREFECT_BASIC_AUTH_USER`: Caddy username for Prefect UI/API.
- `PREFECT_BASIC_AUTH_HASH`: Caddy-compatible bcrypt password hash.
- `PUSHOVER_APP_TOKEN`: Prefect daily brief notifications.
- `PUSHOVER_USER_KEY`: Prefect daily brief notifications.
- `GEMINI_API_KEY`: Prefect daily brief rewrite support.
- `AIRFLOW_POSTGRES_PASSWORD`: Airflow PostgreSQL password.
- `AIRFLOW__CORE__FERNET_KEY`: Airflow secret for encrypted values.
- `AIRFLOW__WEBSERVER__SECRET_KEY`: Airflow webserver/session secret.
- `AIRFLOW_ADMIN_USER`: Airflow admin username.
- `AIRFLOW_ADMIN_PASSWORD`: Airflow admin password.
- `ACME_EMAIL`: Caddy ACME registration email.
- `DIGITALOCEAN_ACCESS_TOKEN`: Terraform provider token. The GitHub deploy workflow also uses it to inspect DigitalOcean resources and add/remove the temporary SSH firewall rule.
- `DO_SSH_KEY_FINGERPRINTS`: GitHub environment variable or secret containing a Terraform list of SSH key fingerprints allowed on the Droplet, for example `["aa:bb:cc"]`.
- `ALLOWED_SSH_CIDRS`: GitHub environment variable or secret containing a Terraform list of stable SSH source CIDRs for the Droplet firewall, for example `["203.0.113.10/32"]` or `[]`.
- `PLATFORM_SSH_USER`: SSH user for deploy, usually `root` for the initial Droplet.
- `PLATFORM_SSH_PORT`: SSH port for deploy, usually `22`.
- `PLATFORM_SSH_PRIVATE_KEY`: Private key authorized on the Droplet for deployment.
- `PLATFORM_ENV_FILE`: Complete production environment file content for `/opt/platform/.env.production`.

`PLATFORM_SSH_HOST` and `PLATFORM_FIREWALL_ID` are no longer required. The deploy workflow reads the Droplet IP and firewall ID from Terraform outputs.

## Rotation Notes

Rotate app API keys at the provider first, then update `.env.production` and restart only the affected service where possible.

Rotate database passwords during a maintenance window. Update the relevant Postgres user password and Compose env file together.

Rotate Airflow `FERNET_KEY` using Airflow's documented key rotation process; replacing it blindly can make encrypted connection values unreadable.

Generate Caddy hashes with:

```bash
caddy hash-password --plaintext 'new-password'
```

When a Caddy bcrypt hash is stored in a Compose `--env-file`, escape dollar signs as `$$` so Compose does not treat hash segments as variable interpolation.

## Production Env File

`PLATFORM_ENV_FILE` should contain the same variable names as `.env.example`, with production values. Do not include comments with secret values in this secret; keep it as plain `KEY=value` lines.
