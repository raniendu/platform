# Repository Guidelines

## Project Structure & Module Organization
Core flow code lives in `flows/` (for example `flows/daily_brief.py`). Runtime configuration is in `config/`, mainly `config/settings.py` (Pydantic models and environment detection). Infrastructure and operations code is split across `terraform/` (DigitalOcean IaC), `docker/` (Nginx, worker, certbot), and `scripts/` (local stack, Pushover credential validation, flow deployment). Tests are in `tests/`, with active suites under `tests/property/` and `tests/integration/`. Reference docs are in `docs/`, and CI workflows are in `.github/workflows/`.

## Build, Test, and Development Commands
- `uv sync`: install project and dev dependencies from `pyproject.toml`/`uv.lock`.
- `./scripts/local-up.sh`: start local Prefect server, PostgreSQL, and worker via `docker-compose.local.yml`.
- `./scripts/local-down.sh`: stop the local stack.
- `python flows/daily_brief.py`: run a flow directly against your configured Prefect API.
- `python scripts/deploy-flows.py`: register flows as deployments.
- `pytest tests/`: run all tests.
- `pytest tests/property/` and `pytest tests/integration/`: run focused suites.
- `docker compose -f docker-compose.local.yml logs -f`: follow service logs while debugging.

## Coding Style & Naming Conventions
Use Python 3.10+ with PEP 8 defaults: 4-space indentation, `snake_case` for functions/files, `PascalCase` for classes, and explicit type hints on public functions. Keep flows in `flows/*.py` and prefer descriptive flow names via `@flow(name="...")`. Centralize environment-dependent values in `config/settings.py` instead of hardcoding in flows or scripts.

## Testing Guidelines
`pytest` is configured to discover `test_*.py` and `test_*` functions under `tests/`. Property-based tests use Hypothesis; keep generated data constrained and deterministic where possible. Add/update tests with any flow registration, config, Docker, or Terraform behavior change. Before opening a PR, run `pytest tests/` locally and validate the local stack with `./scripts/local-up.sh`.

## Commit & Pull Request Guidelines
Follow the existing Conventional Commit pattern seen in history: `feat:`, `fix:`, `chore:`, `docs:`, `ci:` with optional scopes (example: `fix(docker): ...`). Keep commits focused and avoid mixing infra, flow logic, and docs in one commit when possible. PRs should include:
- a concise summary of behavior changes,
- related issue/context,
- local verification steps and command output summary,
- screenshots only when UI/access behavior changes (for example Prefect UI or deployment dashboard views).

## Security & Configuration Tips
Do not commit secrets. Keep local secrets in `.env`; use GitHub Secrets for CI/CD and Terraform variables. Validate production-related changes against `docker-compose.prod.yml` and `terraform/terraform.tfvars.example` before merge.
