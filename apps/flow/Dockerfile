# Use official Apache Airflow base image with pinned version
FROM apache/airflow:3.1.7-python3.10

# Set working directory
WORKDIR /opt/airflow

# Copy DAGs and other application files
COPY --chown=airflow:root dags ./dags/

# Set environment variables
ENV AIRFLOW__CORE__LOAD_EXAMPLES=False
ENV AIRFLOW__CORE__DAGS_FOLDER=/opt/airflow/dags

# Expose Airflow webserver port
EXPOSE 8080
