# syntax=docker/dockerfile:1.7
# Debian trixie ships SQLite 3.46+; bookworm's 3.40 hits a DBOS schema-migration
# IntegrityError on first run. Stay on trixie until upstream pins or fixes.
FROM ghcr.io/astral-sh/uv:python3.13-trixie
LABEL org.opencontainers.image.source="https://github.com/raniendu/platform/tree/main/apps/raman"
LABEL org.opencontainers.image.description="Personal Pydantic AI agent — CLI + FastAPI HTTP surface."
LABEL org.opencontainers.image.licenses="MIT"

ENV UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    RAMAN_DB_PATH=/app/.raman/raman.sqlite3

WORKDIR /app

# Resolve runtime dependencies first so this layer caches across code edits.
# --no-install-project skips building the raman wheel; source isn't here yet.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

ENV PATH="/app/.venv/bin:$PATH"

# Application code and agent specs. Tests/evals/docs are excluded via .dockerignore.
COPY raman ./raman
COPY spec ./spec

# Now install the raman project itself; deps layer above is cached.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# DBOS + ThreadStore live under /app/.raman by default; mount a volume here to persist state.
RUN mkdir -p /app/.raman

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["uvicorn", "raman.api:app", "--host", "0.0.0.0", "--port", "8000"]
