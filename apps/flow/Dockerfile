# Use official Apache Airflow base image with pinned version
FROM apache/airflow:3.1.7-python3.10

# Switch to root to install UV
USER root

# Install UV for fast Python package management
RUN apt-get update && \
    apt-get install -y curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    cp /root/.local/bin/uv /usr/local/bin/uv && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /opt/airflow

# Copy dependency files
COPY --chown=airflow:root pyproject.toml ./

# Install dependencies using UV (as root to install system-wide)
RUN uv pip install --system -e .

# Switch back to airflow user
USER airflow

# Copy DAGs and other application files
COPY --chown=airflow:root dags ./dags/

# Set environment variables
ENV AIRFLOW__CORE__LOAD_EXAMPLES=False
ENV AIRFLOW__CORE__DAGS_FOLDER=/opt/airflow/dags

# Expose Airflow webserver port
EXPOSE 8080
