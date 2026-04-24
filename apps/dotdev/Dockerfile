FROM ghcr.io/astral-sh/uv:python3.13-bookworm
LABEL authors="raniendu"

# Set the working directory in the container
WORKDIR /app

# Copy project metadata first and resolve dependencies
COPY pyproject.toml uv.lock ./

# Create a virtualenv and install only runtime deps (no dev)
RUN uv sync --frozen --no-dev

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

# Command to run the app with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8501", "app:app"]
