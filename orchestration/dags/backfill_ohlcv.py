"""DAG de backfill OHLCV : télécharge l'historique complet Binance → MinIO → PostgreSQL.

Ce DAG est conçu pour un déclenchement MANUEL uniquement (schedule_interval=None).
Il ne tournera jamais tout seul — vous l'activez quand vous en avez besoin.

Par défaut : 2 ans d'historique à 1h pour BTCUSDC et ETHUSDC.
Les symboles, l'intervalle et les dates sont configurables au déclenchement.

── Déclenchement via l'interface Airflow ──────────────────────────────────────
    DAGs → backfill_ohlcv_binance → bouton "Trigger DAG ▶"
    (les valeurs par défaut des paramètres s'appliquent)

── Déclenchement via CLI avec paramètres personnalisés ────────────────────────
    airflow dags trigger backfill_ohlcv_binance \\
        --conf '{
            "symbols":    ["BTCUSDC", "ETHUSDC", "BNBUSDC"],
            "interval":   "1h",
            "start_date": "2024-06-01",
            "end_date":   "2026-06-12"
        }'

── Paramètres (modifiables au déclenchement) ──────────────────────────────────
    symbols    : liste de paires de trading
    interval   : intervalle temporel (1m / 5m / 15m / 1h / 4h / 1d)
    start_date : date de début ISO (YYYY-MM-DD). Défaut : 2 ans en arrière.
    end_date   : date de fin ISO (YYYY-MM-DD).   Défaut : heure courante.

── Estimation durée ────────────────────────────────────────────────────────────
    2 ans × 1h × 1 symbole ≈ 17 520 bougies → 18 chunks → ~10 secondes.
    Plusieurs symboles s'exécutent en parallèle (tâches Airflow indépendantes).
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import du job de backfill
# ---------------------------------------------------------------------------

JOBS_PATH = "/opt/airflow/jobs"
if JOBS_PATH not in sys.path:
    sys.path.insert(0, JOBS_PATH)

try:
    from backfill.backfill_ohlcv import run_backfill
    _JOB_AVAILABLE = True
except ImportError as exc:
    logger.warning("backfill job non disponible: %s", exc)
    _JOB_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration par défaut — modifiable sans toucher au DAG via les params
# ---------------------------------------------------------------------------

DEFAULT_SYMBOLS = ["BTCUSDC", "ETHUSDC"]
DEFAULT_INTERVAL = "1h"
DEFAULT_YEARS = 2

_now = datetime.now(UTC)
_default_start = (_now - timedelta(days=365 * DEFAULT_YEARS)).strftime("%Y-%m-%d")
_default_end = _now.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Factory de tâche
# ---------------------------------------------------------------------------

def _make_backfill_callable(symbol: str):
    """Retourne un callable Airflow pour le symbole donné."""
    def backfill_task(**context):
        if not _JOB_AVAILABLE:
            raise RuntimeError(
                f"Le job backfill_ohlcv n'est pas disponible. "
                f"Vérifier que {JOBS_PATH}/backfill/backfill_ohlcv.py est monté."
            )

        params = context.get("params", {})
        interval = params.get("interval", DEFAULT_INTERVAL)
        start_date_str = params.get("start_date", _default_start)
        end_date_str = params.get("end_date", _default_end)

        start_dt = datetime.fromisoformat(start_date_str).replace(tzinfo=UTC)
        end_dt = datetime.fromisoformat(end_date_str).replace(tzinfo=UTC)

        logger.info(
            "backfill_task  symbol=%s  interval=%s  [%s → %s]",
            symbol, interval, start_date_str, end_date_str,
        )

        stats = run_backfill(
            symbol=symbol,
            interval=interval,
            start_dt=start_dt,
            end_dt=end_dt,
        )

        logger.info(
            "backfill_task done  symbol=%s  rows=%s  chunks_ok=%s  "
            "chunks_fail=%s  duration=%ss",
            symbol,
            stats["total_rows"],
            stats["chunks_processed"],
            stats["chunks_failed"],
            stats["duration_s"],
        )

        if stats["chunks_failed"] > 0:
            raise RuntimeError(
                f"{stats['chunks_failed']} chunk(s) en échec pour {symbol}. "
                f"Données manquantes — relancez la tâche pour récupérer les trous."
            )

        return {
            "symbol": symbol,
            "total_rows": stats["total_rows"],
            "chunks_processed": stats["chunks_processed"],
            "duration_s": stats["duration_s"],
        }

    backfill_task.__name__ = f"backfill_{symbol}_{DEFAULT_INTERVAL}"
    return backfill_task


# ---------------------------------------------------------------------------
# Définition du DAG
# ---------------------------------------------------------------------------

default_args = {
    "owner": "cryptobot",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=2),
}

with DAG(
    dag_id="backfill_ohlcv_binance",
    default_args=default_args,
    description=(
        "Backfill historique OHLCV depuis Binance (jusqu'à 2 ans, au pas 1h). "
        "Déclenché manuellement. Configurable via les paramètres du DAG."
    ),
    schedule_interval=None,   # déclenchement manuel uniquement
    catchup=False,
    max_active_runs=1,
    tags=["backfill", "binance", "minio", "postgres", "historique"],
    params={
        "symbols": DEFAULT_SYMBOLS,
        "interval": DEFAULT_INTERVAL,
        "start_date": _default_start,
        "end_date": _default_end,
    },
) as dag:
    # Une tâche par symbole — elles s'exécutent en parallèle
    for _sym in DEFAULT_SYMBOLS:
        PythonOperator(
            task_id=f"backfill_{_sym}_{DEFAULT_INTERVAL}",
            python_callable=_make_backfill_callable(_sym),
            provide_context=True,
        )
