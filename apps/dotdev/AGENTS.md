# DotDev App Agent Guide

## Scope

This guide applies inside `apps/dotdev/`. The root `AGENTS.md` remains authoritative for shared monorepo, deployment, infrastructure, and secret-handling rules.

## Project Shape

- `app.py`: Flask app entrypoint and route handlers.
- `templates/`: Jinja2 HTML templates.
- `static/`: CSS, JavaScript, images, documents, and other assets.
- `posts/`: Markdown sources for the Posts timeline.
- `tests/`: pytest tests.
- `Dockerfile`: image source used by the shared platform workflows.

There is no standalone App Platform deployment for this app anymore.

## Commands

Run from the repository root:

```bash
uv sync --project apps/dotdev
uv run --project apps/dotdev pytest apps/dotdev/tests -q
```

Local app-only run:

```bash
uv run --project apps/dotdev flask --app app run --host 0.0.0.0 --port 5000
```

Shared local platform:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local logs -f dotdev
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down
```

## Development Rules

- Python runtime is 3.13 for this app.
- Keep templates in `templates/` and static assets in `static/`.
- Posts must include YAML front matter with `title`, `date`, and `tags`.
- Run the DotDev test suite after route, post-rendering, or template changes.

## Deployment Boundary

Production DotDev runs in the shared platform stack on `platform-shared`, behind Caddy at `https://raniendu.dev`.

Do not add standalone App Platform instructions here. Production deploys use the root `.github/workflows/deploy.yml` workflow after review and environment approval.
