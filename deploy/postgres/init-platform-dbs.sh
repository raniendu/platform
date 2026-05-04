#!/usr/bin/env bash
set -euo pipefail

create_app_database() {
  local app_user="$1"
  local app_password="$2"
  local app_database="$3"

  psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set=app_user="$app_user" \
    --set=app_password="$app_password" \
    --set=app_database="$app_database" \
    --set=ON_ERROR_STOP=1 <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_password')
WHERE NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = :'app_user'
) \gexec

SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_password') \gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'app_database', :'app_user')
WHERE NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_database WHERE datname = :'app_database'
) \gexec
SQL

  psql --username "$POSTGRES_USER" --dbname "$app_database" \
    --set=app_user="$app_user" \
    --set=app_database="$app_database" \
    --set=ON_ERROR_STOP=1 <<'SQL'
GRANT ALL PRIVILEGES ON DATABASE :"app_database" TO :"app_user";
GRANT ALL ON SCHEMA public TO :"app_user";
ALTER SCHEMA public OWNER TO :"app_user";
SQL
}

create_app_database prefect "$PREFECT_POSTGRES_PASSWORD" prefect
create_app_database airflow "$AIRFLOW_POSTGRES_PASSWORD" airflow
create_app_database paperclip "$PAPERCLIP_POSTGRES_PASSWORD" paperclip
