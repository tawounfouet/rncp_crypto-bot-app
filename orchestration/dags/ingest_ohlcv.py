"""DAG d'ingestion OHLCV : Binance → MinIO.

Collecte les klines OHLCV pour les paires configurées et les stocke
dans MinIO sous la convention raw/ohlcv/<SYMBOL>/<interval>/<date>.parquet.

Planning : toutes les heures
Rétention : 7 jours de logs Airflow

Variables Airflow utilisées :
    Aucune — tout passe par les variables d'environnement du conteneur
    (héritées du docker-compose.yml via x-airflow-common).

Flux du DAG :
    start → collect_BTCUSDT_1h ─┐
                                  ├→ notify_success
            collect_ETHUSDT_1h ─┘
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import du job d'ingestion
# Airflow monte /opt/airflow/jobs → on ajoute ce chemin au sys.path
# ---------------------------------------------------------------------------

JOBS_PATH = "/opt/airflow/jobs"
if JOBS_PATH not in sys.path:
    sys.path.insert(0, JOBS_PATH)

# Import dynamique pour éviter les erreurs si le dossier n'est pas encore monté
try:
    from ingest.collect_ohlcv import run_ingestion
    _JOB_AVAILABLE = True
except ImportError as exc:
    logger.warning("collect_ohlcv job non disponible: %s", exc)
    _JOB_AVAILABLE = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Symboles et intervalles à collecter — modifiable sans toucher au DAG
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
INTERVAL = "1h"
LIMIT = 1000   # klines par run (max API Binance = 1000)


def _make_collect_callable(symbol: str, interval: str, limit: int):
    """Retourne un callable pour PythonOperator (closure propre par symbole)."""
    def collect():
        if not _JOB_AVAILABLE:
            raise RuntimeError(
                "Le job collect_ohlcv n'est pas disponible. "
                f"Vérifier que {JOBS_PATH}/ingest/collect_ohlcv.py est monté."
            )
        object_key = run_ingestion(symbol=symbol, interval=interval, limit=limit)
        logger.info("ingestion ok symbol=%s object_key=%s", symbol, object_key)
        return object_key
    collect.__name__ = f"collect_{symbol}_{interval}"
    return collect


# ---------------------------------------------------------------------------
# Définition du DAG
# ---------------------------------------------------------------------------

default_args = {
    "owner": "cryptobot",
    "depends_on_past": False,
    "start_date": datetime(2026, 6, 9),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
}

with DAG(
    dag_id="ingest_ohlcv_binance_to_minio",
    default_args=default_args,
    description=(
        "Collecte les klines OHLCV depuis Binance (API publique) "
        "et les stocke dans MinIO (raw/ohlcv/<SYMBOL>/<interval>/<date>.parquet)."
    ),
    schedule_interval="@hourly",
    catchup=False,
    max_active_runs=1,         # évite les runs parallèles qui écraseraient le même fichier
    tags=["ingestion", "binance", "minio", "raw"],
) as dag:

    # Créer une tâche de collecte par symbole (exécution parallèle)
    collect_tasks = []
    for symbol in SYMBOLS:
        task = PythonOperator(
            task_id=f"collect_{symbol}_{INTERVAL}",
            python_callable=_make_collect_callable(symbol, INTERVAL, LIMIT),
        )
        collect_tasks.append(task)

    # Les tâches de collecte sont indépendantes → exécution parallèle par défaut
    # Pour forcer la séquentialité (éviter le rate-limiting Binance) :
    # for i in range(len(collect_tasks) - 1):
    #     collect_tasks[i] >> collect_tasks[i + 1]
