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
    from transform.load_ohlcv import run_loading
    _JOB_AVAILABLE = True
except ImportError as exc:
    logger.warning("jobs non disponibles (collect_ohlcv ou load_ohlcv): %s", exc)
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


def _make_load_callable(symbol: str, interval: str):
    """Retourne un callable pour PythonOperator qui charge les données depuis MinIO vers PostgreSQL."""
    def load(ti):
        if not _JOB_AVAILABLE:
            raise RuntimeError(
                "Le job load_ohlcv n'est pas disponible. "
                f"Vérifier que {JOBS_PATH}/transform/load_ohlcv.py est monté."
            )
        # Récupérer la clé d'objet MinIO retournée par la tâche collect
        object_key = ti.xcom_pull(task_ids=f"collect_{symbol}_{interval}")
        if not object_key:
            raise ValueError(f"Aucune clé d'objet MinIO trouvée pour la tâche collect_{symbol}_{interval}")

        logger.info("Démarrage du chargement PostgreSQL pour symbol=%s, object_key=%s", symbol, object_key)
        run_loading(object_key=object_key)
        logger.info("Chargement complet pour symbol=%s, object_key=%s", symbol, object_key)
    load.__name__ = f"load_{symbol}_{interval}"
    return load


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
        "Collecte les klines OHLCV depuis Binance (API publique), "
        "les stocke dans MinIO et les charge dans PostgreSQL."
    ),
    schedule_interval="@hourly",
    catchup=False,
    max_active_runs=1,         # évite les runs parallèles qui écraseraient le même fichier
    tags=["ingestion", "binance", "minio", "raw", "postgres"],
) as dag:

    # Créer les tâches de collecte et de chargement pour chaque symbole
    for symbol in SYMBOLS:
        collect_task = PythonOperator(
            task_id=f"collect_{symbol}_{INTERVAL}",
            python_callable=_make_collect_callable(symbol, INTERVAL, LIMIT),
        )

        load_task = PythonOperator(
            task_id=f"load_{symbol}_{INTERVAL}",
            python_callable=_make_load_callable(symbol, INTERVAL),
        )

        collect_task >> load_task
