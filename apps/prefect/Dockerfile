# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:python3.10-bookworm

ENV UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

COPY config ./config
COPY flows ./flows
COPY scripts ./scripts
COPY docker ./docker

RUN chmod +x /app/docker/prefect/start-worker.sh /app/scripts/deploy-flows.py

EXPOSE 4200
