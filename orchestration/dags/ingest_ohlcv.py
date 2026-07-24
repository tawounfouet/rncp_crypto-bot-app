"""DAGs d'ingestion OHLCV multi-exchange : <exchange> → MinIO → PostgreSQL.

Un DAG est généré **par exchange** à partir de ``INGESTION_TARGETS``. Chaque DAG
collecte les klines des paires configurées et les stocke dans MinIO sous la
convention ``raw/ohlcv/<exchange>/<SYMBOL>/<interval>/<date>.parquet``, puis les
charge dans PostgreSQL (table ``market_data``, déjà scopée par exchange).

Planning : toutes les heures. Ajouter un exchange = une entrée dans INGESTION_TARGETS.

Flux (par DAG) :
    collect_<exchange>_<SYMBOL>_<interval> → load_<exchange>_<SYMBOL>_<interval>
"""

from __future__ import annotations

import logging
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
# Configuration — un DAG par exchange, éditable sans toucher au reste du code
# ---------------------------------------------------------------------------

#: Cibles d'ingestion. Ajouter un exchange = ajouter une entrée ici.
#: (paires par exchange : Binance en USDT, Kraken en EUR — cf. contexte MiCA #13)
INGESTION_TARGETS = [
    {"exchange": "binance", "symbols": ["BTCUSDT", "ETHUSDT"], "interval": "1h"},
    {"exchange": "kraken", "symbols": ["BTCEUR", "ETHEUR"], "interval": "1h"},
]
LIMIT = 1000  # klines par run (max API = 1000)


def _make_collect_callable(exchange: str, symbol: str, interval: str, limit: int):
    """Callable PythonOperator pour la collecte (closure propre par exchange/symbole)."""

    def collect():
        if not _JOB_AVAILABLE:
            raise RuntimeError(
                f"Le job collect_ohlcv n'est pas disponible. Vérifier {JOBS_PATH}/ingest/collect_ohlcv.py."
            )
        object_key = run_ingestion(symbol=symbol, interval=interval, limit=limit, exchange=exchange)
        logger.info("ingestion ok exchange=%s symbol=%s object_key=%s", exchange, symbol, object_key)
        return object_key

    collect.__name__ = f"collect_{exchange}_{symbol}_{interval}"
    return collect


def _make_load_callable(exchange: str, symbol: str, interval: str):
    """Callable PythonOperator pour le chargement MinIO → PostgreSQL."""

    def load(ti):
        if not _JOB_AVAILABLE:
            raise RuntimeError(
                f"Le job load_ohlcv n'est pas disponible. Vérifier {JOBS_PATH}/transform/load_ohlcv.py."
            )
        # Clé d'objet MinIO retournée par la tâche collect correspondante
        task_id = f"collect_{exchange}_{symbol}_{interval}"
        object_key = ti.xcom_pull(task_ids=task_id)
        if not object_key:
            raise ValueError(f"Aucune clé d'objet MinIO trouvée pour la tâche {task_id}")
        logger.info("load start exchange=%s symbol=%s object_key=%s", exchange, symbol, object_key)
        run_loading(object_key=object_key)
        logger.info("load complete exchange=%s symbol=%s object_key=%s", exchange, symbol, object_key)

    load.__name__ = f"load_{exchange}_{symbol}_{interval}"
    return load


# ---------------------------------------------------------------------------
# Génération des DAGs (un par exchange)
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

for _target in INGESTION_TARGETS:
    _exchange = _target["exchange"]
    _interval = _target["interval"]
    _dag_id = f"ingest_ohlcv_{_exchange}_to_minio"

    with DAG(
        dag_id=_dag_id,
        default_args=default_args,
        description=f"Collecte OHLCV depuis {_exchange} (API publique), stocke dans MinIO et charge dans PostgreSQL.",
        schedule_interval="@hourly",
        catchup=False,
        max_active_runs=1,  # évite les runs parallèles qui écraseraient le même fichier
        tags=["ingestion", _exchange, "minio", "raw", "postgres"],
    ) as dag:
        for _symbol in _target["symbols"]:
            _collect = PythonOperator(
                task_id=f"collect_{_exchange}_{_symbol}_{_interval}",
                python_callable=_make_collect_callable(_exchange, _symbol, _interval, LIMIT),
            )
            _load = PythonOperator(
                task_id=f"load_{_exchange}_{_symbol}_{_interval}",
                python_callable=_make_load_callable(_exchange, _symbol, _interval),
            )
            _collect >> _load

    # Airflow découvre les DAGs dans les variables globales du module
    globals()[_dag_id] = dag
