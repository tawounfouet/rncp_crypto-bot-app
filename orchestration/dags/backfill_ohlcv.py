"""DAGs de backfill OHLCV : téléchargent l'historique complet exchange → MinIO → PostgreSQL.

Un DAG par exchange (meme principe que orchestration/dags/ingest_ohlcv.py::INGESTION_TARGETS),
conçus pour un déclenchement MANUEL uniquement (schedule_interval=None). Ils ne tournent
jamais tout seuls — on les active quand on en a besoin.

Par défaut : 2 ans d'historique à 1h pour les paires de BACKFILL_TARGETS. Les symboles,
l'intervalle et les dates sont configurables au déclenchement.

── Déclenchement via l'interface Airflow ──────────────────────────────────────
    DAGs → backfill_ohlcv_binance (ou backfill_ohlcv_kraken) → bouton "Trigger DAG ▶"
    (les valeurs par défaut des paramètres s'appliquent)

── Déclenchement via CLI avec paramètres personnalisés ────────────────────────
    airflow dags trigger backfill_ohlcv_binance \\
        --conf '{
            "symbols":    ["BTCUSDC", "ETHUSDC", "BNBUSDC"],
            "start_date": "2024-06-01",
            "end_date":   "2026-06-12"
        }'

── Paramètres (modifiables au déclenchement) ──────────────────────────────────
    symbols    : liste de paires de trading
    start_date : date de début ISO (YYYY-MM-DD). Défaut : 2 ans en arrière.
    end_date   : date de fin ISO (YYYY-MM-DD).   Défaut : heure courante.

    L'intervalle n'est PLUS un parametre runtime (regression corrigee le 2026-08-29 :
    le task_id etait fige sur "_1h" quel que soit l'interval demande en conf, rendant
    le graphe Airflow trompeur -- une tache par intervalle de BACKFILL_INTERVALS existe
    desormais, toutes executees a chaque declenchement du DAG.

── Estimation durée ────────────────────────────────────────────────────────────
    2 ans × 1h × 1 symbole ≈ 17 520 bougies → 18 chunks → ~10 secondes.
    Plusieurs symboles s'exécutent en parallèle (tâches Airflow indépendantes).
"""

from __future__ import annotations

import logging
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
# Configuration — un DAG par exchange, éditable sans toucher au reste du code.
# Mêmes paires que orchestration/dags/ingest_ohlcv.py::INGESTION_TARGETS (Binance en
# USDC, Kraken en EUR — cf. contexte MiCA #13).
# ---------------------------------------------------------------------------

BACKFILL_TARGETS = [
    {"exchange": "binance", "symbols": ["BTCUSDC", "ETHUSDC"]},
    {"exchange": "kraken", "symbols": ["BTCEUR", "ETHEUR"]},
]
# A garder synchronise avec models/config.yaml::data.intervals et orchestration/dags/
# ml_pipeline.py::INTERVALS -- une tache par (symbole, interval) est generee ci-dessous,
# toutes executees a chaque declenchement du DAG (plus simple/fiable qu'un param runtime,
# cf. regression du 2026-08-29 : task_id fige sur "_1h" quel que soit l'interval demande).
BACKFILL_INTERVALS = ["1h", "5m", "1d"]
DEFAULT_YEARS = 2

_now = datetime.now(UTC)
_default_start = (_now - timedelta(days=365 * DEFAULT_YEARS)).strftime("%Y-%m-%d")
_default_end = _now.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Factory de tâche
# ---------------------------------------------------------------------------


def _make_backfill_callable(exchange: str, symbol: str, interval: str):
    """Retourne un callable Airflow pour le triplet exchange/symbole/interval donné."""

    def backfill_task(**context):
        if not _JOB_AVAILABLE:
            raise RuntimeError(
                f"Le job backfill_ohlcv n'est pas disponible. "
                f"Vérifier que {JOBS_PATH}/backfill/backfill_ohlcv.py est monté."
            )

        params = context.get("params", {})
        start_date_str = params.get("start_date", _default_start)
        end_date_str = params.get("end_date", _default_end)

        start_dt = datetime.fromisoformat(start_date_str).replace(tzinfo=UTC)
        end_dt = datetime.fromisoformat(end_date_str).replace(tzinfo=UTC)

        logger.info(
            "backfill_task  exchange=%s  symbol=%s  interval=%s  [%s → %s]",
            exchange,
            symbol,
            interval,
            start_date_str,
            end_date_str,
        )

        stats = run_backfill(
            symbol=symbol,
            interval=interval,
            start_dt=start_dt,
            end_dt=end_dt,
            exchange=exchange,
        )

        logger.info(
            "backfill_task done  exchange=%s  symbol=%s  rows=%s  chunks_ok=%s  "
            "chunks_fail=%s  duration=%ss",
            exchange,
            symbol,
            stats["total_rows"],
            stats["chunks_processed"],
            stats["chunks_failed"],
            stats["duration_s"],
        )

        if stats["chunks_failed"] > 0:
            raise RuntimeError(
                f"{stats['chunks_failed']} chunk(s) en échec pour {exchange}/{symbol}. "
                f"Données manquantes — relancez la tâche pour récupérer les trous."
            )

        return {
            "symbol": symbol,
            "total_rows": stats["total_rows"],
            "chunks_processed": stats["chunks_processed"],
            "duration_s": stats["duration_s"],
        }

    backfill_task.__name__ = f"backfill_{exchange}_{symbol}_{interval}"
    return backfill_task


# ---------------------------------------------------------------------------
# Génération des DAGs (un par exchange)
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

for _target in BACKFILL_TARGETS:
    _exchange = _target["exchange"]
    _symbols = _target["symbols"]
    _dag_id = f"backfill_ohlcv_{_exchange}"

    with DAG(
        dag_id=_dag_id,
        default_args=default_args,
        description=(
            f"Backfill historique OHLCV depuis {_exchange} (jusqu'à 2 ans, sur {BACKFILL_INTERVALS}). "
            "Déclenché manuellement. Configurable via les paramètres du DAG."
        ),
        schedule_interval=None,  # déclenchement manuel uniquement
        catchup=False,
        max_active_runs=1,
        tags=["backfill", _exchange, "minio", "postgres", "historique"],
        params={
            "symbols": _symbols,
            "start_date": _default_start,
            "end_date": _default_end,
        },
    ) as dag:
        # Une tâche par couple (symbole, interval) — elles s'exécutent en parallèle
        for _sym in _symbols:
            for _interval in BACKFILL_INTERVALS:
                PythonOperator(
                    task_id=f"backfill_{_exchange}_{_sym}_{_interval}",
                    python_callable=_make_backfill_callable(_exchange, _sym, _interval),
                    provide_context=True,
                )

    globals()[_dag_id] = dag
