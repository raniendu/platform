# Repository Guidelines

## Project Structure & Module Organization

`raman/` contains the package code:

- `agent.py` builds the Pydantic AI agent from a spec, settings, and `TOOL_REGISTRY`.
- `api.py` exposes FastAPI routes (`/chat`, `/threads/...`, `/events/...`, `/telegram/webhook`, `/healthz`).
- `cli.py` defines the `raman` command.
- `context.py` provides runtime instruction injectors (agent identity, current datetime).
- `settings.py` loads environment configuration via Pydantic Settings.
- `spec.py` loads TOML agent specs and assembles the instructions block.
- `tools.py` defines `TOOL_REGISTRY`, the name → async callable map specs reference.
- `gateway.py` holds `ThreadStore` (SQLite) and `ConversationService`, plus CloudEvent helpers used by the threaded interface.
- `dbos_gateway.py` wires DBOS workflows and queues for inbound message processing and outbound delivery.
- `telegram.py` implements the Telegram webhook adapter (parse, dedupe, allowlist, commands, send).

Agent definitions live under `spec/<agent>/`; the default agent is `spec/raman/agent.toml` with its prompt in `system_prompt.md`. Optional cross-agent context lives under `spec/shared/`. Tests are in `tests/`, LLM evaluation helpers are in `evals/`, and topical guides live in `docs/` (`tools.md`, `threaded_conversations.md`, `telegram_live_testing.md`, `architecture_roadmap.md`).

## Build, Test, and Development Commands

- `uv sync`: install runtime and development dependencies from `pyproject.toml` and `uv.lock`.
- `uv run raman`: start the interactive CLI for the default agent.
- `uv run raman --agent <name>`: run an alternate spec from `spec/<name>/`.
- `uv run raman-api`: start the FastAPI app on `http://127.0.0.1:8000`.
- `uv run pytest`: run the offline unit test suite.
- `RAMAN_RUN_EVALS=1 uv run pytest tests/test_evals.py`: run live LLM-judge tests; requires Ollama and the configured model.
- `uv run python -m evals.run`: run the standalone evaluation report.
- `uv run pre-commit run --all-files`: run Black and isort formatting checks.

## Coding Style & Naming Conventions

Use Python 3.13 features and keep type hints on public helpers and boundaries. Formatting is Black with an 88-character line length; imports are sorted by isort using the Black profile. Follow existing names: modules and functions use `snake_case`, classes use `PascalCase`, and environment variables use `RAMAN_*` or provider-specific uppercase names. Keep agent tool names stable because specs reference them through `raman.tools.TOOL_REGISTRY`.

## Testing Guidelines

Tests use `pytest` with `pytest-asyncio` in auto mode. Place tests in `tests/` and name files `test_<area>.py`; test functions should describe the expected behavior, such as `test_chat_rejects_empty_prompt`. Default tests should stay offline and deterministic. Gate model calls, external APIs, or Ollama-dependent checks behind explicit environment variables. Tests that touch the threaded surface should patch `raman.api._get_dispatcher` (or supply a fake `EventDispatcher`) rather than booting DBOS — see `tests/test_api_gateway.py` for the pattern.

## Commit & Pull Request Guidelines

Recent commits use short imperative summaries such as `Add HTTP surface...`; keep new commit messages in that style and scoped to one change. Pull requests should include purpose, key implementation notes, test commands, and configuration or model/runtime assumptions. Link issues when applicable and include example CLI/API output for user-facing changes.

When asked to push changes, do not push directly to `main`; branch, commit, push the branch, and open a pull request.

## Security & Configuration Tips

Use `.env.example` as the template for local configuration and keep real `.env` values private. Do not commit API keys such as `PARALLEL_API_KEY`. Prefer least-privilege defaults when adding tools, endpoints, or new environment settings.
