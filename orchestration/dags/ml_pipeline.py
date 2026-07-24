"""DAG ML Pipeline : features → training → déploiement → vérification.

Enchaîne les étapes du pipeline ML après que les données brutes ont été
ingérées par le DAG ``ingest_ohlcv_binance_to_minio`` :

    start
      ├── build_features_BTCUSDT_1h
      ├── build_features_ETHUSDT_1h
      │
      ├── train_random_forest  (attend toutes les features)
      │
      ├── deploy_model         (copie le meilleur modèle → MinIO)
      │
      └── verify_inference     (appelle l'endpoint backend)

Planning : quotidien à 06:00 UTC (après les runs d'ingestion nocturnes).

Prérequis Docker (docker-compose.yml) :
    Ajouter sous ``x-airflow-common > volumes`` :
        - ./models:/opt/airflow/models
        - ./utils:/opt/airflow/utils
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/opt/airflow")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
UTILS_DIR = os.path.join(PROJECT_ROOT, "utils")

# Les jobs/ sont déjà montés dans Airflow → on peut importer deploy_model
JOBS_PATH = os.path.join(PROJECT_ROOT, "jobs")
if JOBS_PATH not in sys.path:
    sys.path.insert(0, JOBS_PATH)

try:
    from deploy_model import deploy_model as _deploy
    _DEPLOY_AVAILABLE = True
except ImportError:
    _DEPLOY_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
INTERVAL = "1h"
CONFIG_PATH = os.path.join(MODELS_DIR, "config.yaml")

# Dataset processed (output de build_features, input de train-rf)
PROCESSED_DIR = os.path.join(MODELS_DIR, "data", "processed")

BACKEND_HEALTH_URL = os.environ.get(
    "BACKEND_HEALTH_URL", "http://crypto-bot-backend:8009/health"
)
INFERENCE_URL = os.environ.get(
    "INFERENCE_URL", "http://crypto-bot-backend:8009/api/v1/inference"
)

# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------


def _python_env() -> dict[str, str]:
    """Variables d'environnement pour les commandes Python du projet."""
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", f"{UTILS_DIR}:{MODELS_DIR}")
    return env


def _feature_path(symbol: str) -> str:
    return os.path.join(PROCESSED_DIR, symbol.upper(), f"{INTERVAL}_features.parquet")


def _feature_cmd(symbol: str) -> str:
    """Commande Bash pour construire les features d'un symbole."""
    return (
        f"cd {MODELS_DIR} && python -m src.main features "
        f"--config {CONFIG_PATH} "
        f"--symbols {symbol} "
        f"--interval {INTERVAL}"
    )


def _train_cmd() -> str:
    """Commande Bash pour entraîner le Random Forest."""
    dataset = _feature_path(SYMBOLS[0])
    return (
        f"cd {MODELS_DIR} && python -m src.main train-rf "
        f"--config {CONFIG_PATH} "
        f"--dataset {dataset}"
    )


def _deploy_callable() -> None:
    """Appelle le job de déploiement (importé depuis jobs/)."""
    if not _DEPLOY_AVAILABLE:
        raise RuntimeError("deploy_model.py non disponible dans jobs/")
    ok = _deploy(model_name="random_forest")
    if not ok:
        raise RuntimeError("Échec du déploiement du modèle random_forest")


# ---------------------------------------------------------------------------
# Définition du DAG
# ---------------------------------------------------------------------------

default_args = {
    "owner": "cryptobot",
    "depends_on_past": False,
    "start_date": datetime(2026, 6, 10),
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="cryptobot_ml_pipeline",
    default_args=default_args,
    description=(
        "Pipeline ML complet : build features → entraînement Random Forest "
        "→ déploiement du modèle vers MinIO → vérification de l'API d'inférence"
    ),
    schedule_interval="0 6 * * *",       # chaque jour à 06:00 UTC
    catchup=False,
    max_active_runs=1,
    tags=["ml", "training", "deployment", "inference"],
) as dag:

    # -- 1. Build features pour chaque symbole ---------------------------------
    build_tasks = []
    for symbol in SYMBOLS:
        task = BashOperator(
            task_id=f"build_features_{symbol}_{INTERVAL}",
            bash_command=_feature_cmd(symbol),
            env=_python_env(),
            cwd=MODELS_DIR,
            retries=2,
            retry_delay=timedelta(minutes=2),
        )
        build_tasks.append(task)

    # -- 2. Entraînement Random Forest -----------------------------------------
    train_rf = BashOperator(
        task_id="train_random_forest",
        bash_command=_train_cmd(),
        env=_python_env(),
        cwd=MODELS_DIR,
        retries=1,
        retry_delay=timedelta(minutes=5),
    )

    # -- 3. Déploiement vers MinIO ---------------------------------------------
    deploy = PythonOperator(
        task_id="deploy_model",
        python_callable=_deploy_callable,
    )

    # -- 4. Vérification de l'API d'inférence -----------------------------------
    verify = BashOperator(
        task_id="verify_inference",
        bash_command=(
            f"curl -s -o /dev/null -w '%{{http_code}}' "
            f"-X POST {INFERENCE_URL}/predict "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"symbol\": \"{SYMBOLS[0]}\", \"interval\": \"{INTERVAL}\", "
            f"\"features\": {{\"rsi_14\": 50}}}}' "
            f"| grep -q 200 || exit 1"
        ),
    )

    # -- Ordonnancement ---------------------------------------------------------
    # Toutes les features en parallèle → puis training → deploy → verify
    train_rf.set_upstream(build_tasks)
    deploy.set_upstream(train_rf)
    verify.set_upstream(deploy)
