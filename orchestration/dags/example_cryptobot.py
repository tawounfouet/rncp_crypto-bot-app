from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import requests
import logging

default_args = {
    "owner": "cryptobot",
    "depends_on_past": False,
    "start_date": datetime(2026, 6, 1),
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

def _ping_backend():
    url = "http://crypto-bot-backend:8009/health"
    response = requests.get(url)
    if response.status_code == 200:
        logging.info("Backend is healthy")
    else:
        raise Exception(f"Backend unhealthy: {response.status_code}")

def _check_db_orders():
    try:
        pg_hook = PostgresHook(postgres_conn_id="postgres_default")
        connection = pg_hook.get_conn()
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM orders;")
        count = cursor.fetchone()[0]
        logging.info(f"Total orders in DB: {count}")
        cursor.close()
        connection.close()
    except Exception as e:
        logging.warning(f"Could not fetch orders count (table might not exist yet): {e}")

with DAG(
    "cryptobot_health_check",
    default_args=default_args,
    description="Verification reguliere de la sante de l'ecosysteme Cryptobot",
    schedule_interval=timedelta(hours=1),
    catchup=False,
) as dag:

    ping_backend_task = PythonOperator(
        task_id="ping_backend",
        python_callable=_ping_backend,
    )

    check_db_task = PythonOperator(
        task_id="check_db_orders",
        python_callable=_check_db_orders,
    )

    ping_backend_task >> check_db_task
