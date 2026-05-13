# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:python3.13-bookworm
LABEL authors="raniendu"

ENV UV_LINK_MODE=copy

# Set the working directory in the container
WORKDIR /app

# Copy project metadata first and resolve dependencies
COPY pyproject.toml uv.lock ./

# Create a virtualenv and install only runtime deps (no dev)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Ensure the environment uses the project virtualenv
ENV PATH="/app/.venv/bin:$PATH"

# Copy the rest of the application code into the container
COPY ./static ./static
COPY ./templates ./templates
COPY ./posts ./posts
COPY ./app.py ./app.py
COPY ./blog.py ./blog.py

# Expose port 8501
EXPOSE 8501

# Command to run the app with Gunicorn. Log to container stdout/stderr for deploy diagnostics.
CMD ["gunicorn", "--bind", "0.0.0.0:8501", "--workers", "2", "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "app:app"]
