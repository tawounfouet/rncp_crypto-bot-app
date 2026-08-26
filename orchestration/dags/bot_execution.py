"""DAG Bot Execution : declenche l'execution des deployments actifs.

Appelle POST /strategies/deployments/execute-active sur crypto-bot-backend (boucle sur
tous les deployments actifs, tous utilisateurs -- cf. StrategyService.execute_active_deployments).
Planifie toutes les heures. Meme principe que ml_pipeline.py : Airflow orchestre un appel
HTTP, il n'execute pas la logique metier lui-meme.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

STRATEGY_URL = os.environ.get("STRATEGY_URL", "http://crypto-bot-backend:8009/api/v1/strategies")
EXECUTE_ACTIVE_TIMEOUT_SECONDS = 300


def _execute_active_deployments_callable() -> None:
    response = requests.post(
        f"{STRATEGY_URL}/deployments/execute-active",
        timeout=EXECUTE_ACTIVE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    logger.info("execute_active_deployments: %s", response.json())


default_args = {
    "owner": "cryptobot",
    "depends_on_past": False,
    "start_date": datetime(2026, 6, 10),
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="cryptobot_bot_execution",
    default_args=default_args,
    description="Declenche l'execution des deployments de bots actifs (signal ML + ordre eventuel)",
    schedule_interval="0 * * * *",  # toutes les heures
    catchup=False,
    max_active_runs=1,
    tags=["trading", "execution"],
) as dag:
    execute_active = PythonOperator(
        task_id="execute_active_deployments",
        python_callable=_execute_active_deployments_callable,
    )
