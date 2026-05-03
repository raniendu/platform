This directory contains the Flask-based source for the DotDev personal site inside the `platform` monorepo. The current build ships a monochrome design system, sticky navigation with a light/dark toggle, a Leaflet powered travels map, and a client-side contact form.

Production is no longer a standalone App Platform app. DotDev runs in the shared platform stack on the `platform-shared` Droplet, behind Caddy at `https://raniendu.dev`.

## Structure

- `app.py` – Flask application defining routes and page logic.
- `templates/` – Jinja2 templates for HTML pages and shared layout.
- `static/` – CSS, JavaScript, icons, and documents.
- `posts/` – Markdown sources for the Posts timeline (one file per entry).
- `pyproject.toml` – Project metadata and Python dependencies (managed by uv).
- `Dockerfile` – image source used by the shared platform workflows.
- `tests/` – Flask route and rendering tests.

## Running Locally

Requires Python 3.13.

### Shared Local Platform

From the repository root:

```bash
cp .env.example .env.local
uv sync --project apps/dotdev
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local up -d --build
```

Open:

- `http://dotdev.localhost`
- `http://localhost:8501`

Stop the stack:

```bash
docker compose -f deploy/compose/docker-compose.local.yml --env-file .env.local down
```

### App-Only Docker

```bash
docker build . -t dotdev
docker run -p 8501:8501 dotdev
```

### Without Docker (uv)

```bash
# Install deps (creates .venv)
uv sync

# Run in the project venv
uv run flask --app app run --host 0.0.0.0 --port 5000
```

Then open http://127.0.0.1:5000/ and visit the About, Resume, Posts, Travels, and Contact routes to confirm rendering. The Leaflet map defaults to a monochrome-friendly basemap and honours the light/dark toggle.

## Publishing Posts

The Posts page reads Markdown files from the `posts/` directory and renders them into a semantic timeline with a vanilla JavaScript tag filter. Each file needs a small [YAML front matter](https://jekyllrb.com/docs/front-matter/) block:

```markdown
---
title: Your Post Title
date: 2025-01-15
tags:
  - tag-one
  - tag-two
---

Your markdown content lives here. It can include lists, code blocks, and images.
```

- Posts are ordered by the `date` value (newest first).
- Tags show up as monochrome chips and can be filtered via the tag buttons.
- Dropping a new `.md` file into `posts/` is all that's needed—no code changes required.

## Screenshots

Launch the dev server and use Playwright (or the Codex preview tooling) to capture route previews:

```bash
uvx playwright install chromium  # one-time
uvx playwright screenshot --device="Desktop Chrome" --output static/images/screenshots/home.png http://127.0.0.1:5000/
```

Repeat the `screenshot` command for `/about`, `/resume`, `/posts`, `/travels`, and `/contact` to keep the documentation up to date.

## Development Checks

- Sync dependencies: `uv sync --project apps/dotdev`
- Run tests: `uv run --project apps/dotdev pytest apps/dotdev/tests -q`
- Format code from this directory when needed: `uvx black .`
- Sort imports from this directory when needed: `uvx isort .`
- Install Git hooks from the repository root if configured: `uvx pre-commit install`

## Production Deployment

Production deployment is manual from the root workflow, not automatic on every push:

```bash
gh workflow run deploy.yml --repo raniendu/platform --ref main
gh run watch --repo raniendu/platform --exit-status
```

Use the root docs for production work:

- `docs/deployment.md`
- `docs/secrets.md`
- `docs/operations.md`
- `docs/rollback.md`

Do not add standalone App Platform instructions here. Infrastructure writes must go through reviewed PRs and GitHub Actions; local DigitalOcean CLI usage is read-only only.
