# Repository Guidelines

## Project Structure & Module Organization
- `app.py`: Flask app entrypoint and route handlers.
- `templates/`: Jinja2 HTML templates.
- `static/`: CSS, JS, images, and documents.
- `posts/`: Markdown sources for the Posts timeline (YAML front matter required).
- `pyproject.toml`: Project metadata and Python dependencies (managed by uv).
- `Dockerfile`, `docker-compose.yml`: Container build/run configs.
- `tests/`: Add pytest files here (`test_*.py`).
- `.env`: Local environment variables (not committed).

## Build, Test, and Development Commands (uv)
- Python: 3.9
- Install uv (one-time): see https://docs.astral.sh/uv/getting-started/.
- Setup: `uv sync` (creates and manages `.venv` from `pyproject.toml`).
- Run (dev): `uv run flask --app app run` or `uv run python app.py`.
- Test: `uv run pytest -q`.
- Install pre-commit (optional but recommended): `uvx pre-commit install` then `uvx pre-commit run --all-files` for a full check.
- Run (prod-like): `gunicorn --bind 0.0.0.0:8501 app:app`
- Docker (build/run): `docker build -t dotdev . && docker run -p 8501:8501 --env-file .env dotdev`
- Env needed: set `GOOGLE_MAPS_API_KEY` for geocoding features.

## Coding Style & Naming Conventions
- Python: PEP 8, 4‑space indentation, UTF‑8, trailing newline.
- Naming: `snake_case` for functions/vars, `PascalCase` for classes, module filenames in `snake_case.py`.
- Templates: Keep page templates in `templates/` and static assets in `static/`; prefer small, reusable partials.
- Posts: Author entries as Markdown under `posts/` with `title`, `date`, and `tags` in front matter so the React client can render timelines, archives, and the word cloud.
- Formatting: CI runs `uvx black --check .` and `uvx isort --check-only .`; fix locally with `uvx black .` and `uvx isort .` or install the git hook via `uvx pre-commit install`.

## Testing Guidelines
- Framework: pytest with Flask’s test client.
- Location: `tests/` with files named `test_*.py` and functions `test_*`.
- Example: create a client and assert route responses (e.g., `GET /` returns 200).
- Run: `pytest -q` (add pytest to your dev environment).

## Commit & Pull Request Guidelines
- Style: Conventional Commits (seen in history) — e.g., `docs: update README with local run steps`, `chore(deps): bump requests`.
- Messages: Imperative mood, concise subject; optional scope in parentheses.
- PRs: include a clear summary, linked issues, screenshots for UI changes, and notes on config/env changes.
- Checks: ensure app starts locally (or via Docker) and pages render without errors.

## Security & Configuration Tips
- Secrets: never commit API keys; use `.env` for local dev and Compose will load it.
- Example `.env` entry: `GOOGLE_MAPS_API_KEY=your_key_here`.
- Review diffs for accidental secret/credential leakage before pushing.
