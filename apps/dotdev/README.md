This repository contains the Flask-based source for my personal site. The current build ships a monochrome design system, sticky navigation with a light/dark toggle, a Leaflet powered travels map, and a client-side contact form.

## Structure

- `app.py` – Flask application defining routes and page logic.
- `templates/` – Jinja2 templates for HTML pages and shared layout.
- `static/` – CSS, JavaScript, icons, and documents.
- `posts/` – Markdown sources for the Posts timeline (one file per entry).
- `pyproject.toml` – Project metadata and Python dependencies (managed by uv).
- `Dockerfile`, `docker-compose.yml` – Containerization and deployment configuration.

## Running Locally

Requires Python 3.13.

### With Docker

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

Ensure `GOOGLE_MAPS_API_KEY` is set in the environment when using features that require Google Maps.

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

- Format code: `uvx black .`
- Sort imports: `uvx isort .`
- Run tests: `uv run pytest -q`
- Install Git hooks (once): `uvx pre-commit install`; run `uvx pre-commit run --all-files` to format everything
