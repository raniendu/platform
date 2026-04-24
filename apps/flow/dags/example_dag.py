"""
Example DAG demonstrating basic Airflow workflow structure.

This DAG runs daily and executes a simple task chain.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.providers.standard.operators.python import PythonOperator


def print_hello():
    """Simple task that prints a greeting."""
    print("Hello from Airflow!")
    return "Hello executed successfully"


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="example_dag",
    default_args=default_args,
    description="An example DAG to demonstrate Airflow setup",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["example"],
) as dag:
    start = EmptyOperator(task_id="start")

    hello_task = PythonOperator(
        task_id="print_hello",
        python_callable=print_hello,
    )

    end = EmptyOperator(task_id="end")

    start >> hello_task >> end
