"""DAG Purge RGPD : purge hebdomadaire des comptes inactifs.

Appelle POST /users/purge-inactive sur crypto-bot-backend (suppression des comptes
dont ``last_active_at`` est plus ancien que 730 jours -- cf.
UserService.delete_inactive_users_older_than, script manuel backend/src/auth/
purge_inactive_users.py). Planifie chaque dimanche a 03:00 UTC. Meme principe que
bot_execution.py : Airflow orchestre un appel HTTP, il n'execute pas la logique
metier lui-meme (le conteneur Airflow n'heberge pas la stack backend).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://crypto-bot-backend:8009/api/v1")
PURGE_URL = os.environ.get("PURGE_URL", f"{BACKEND_URL}/users/purge-inactive")
# Nombre de jours d'inactivite au-dela duquel un compte est purge (RGPD).
PURGE_INACTIVE_DAYS = int(os.environ.get("PURGE_INACTIVE_DAYS", "730"))
PURGE_TIMEOUT_SECONDS = 300


def _purge_inactive_users_callable() -> None:
    response = requests.post(
        PURGE_URL,
        params={"days": PURGE_INACTIVE_DAYS},
        timeout=PURGE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    logger.info("purge_inactive_users: %s", response.json())


default_args = {
    "owner": "cryptobot",
    "depends_on_past": False,
    "start_date": datetime(2026, 8, 7),
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="cryptobot_purge_inactive_users",
    default_args=default_args,
    description=(
        "Purge RGPD des comptes inactifs depuis plus de "
        f"{PURGE_INACTIVE_DAYS} jours (appel HTTP au backend)"
    ),
    schedule_interval="0 3 * * 0",  # chaque dimanche a 03:00 UTC
    catchup=False,
    max_active_runs=1,
    tags=["rgpd", "users", "purge"],
) as dag:
    purge_inactive = PythonOperator(
        task_id="purge_inactive_users",
        python_callable=_purge_inactive_users_callable,
    )
