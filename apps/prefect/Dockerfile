FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

COPY config ./config
COPY flows ./flows
COPY scripts ./scripts
COPY docker ./docker

RUN chmod +x /app/docker/prefect/start-worker.sh /app/scripts/deploy-flows.py

EXPOSE 4200

