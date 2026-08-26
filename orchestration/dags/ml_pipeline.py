"""DAG ML Pipeline : features → training → déploiement → vérification.

Enchaîne les étapes du pipeline ML après que les données brutes ont été
ingérées par le DAG ``ingest_ohlcv_binance_to_minio`` :

    start
      ├── build_features_BTCUSDC_1h
      ├── build_features_ETHUSDC_1h
      │
      ├── train_random_forest    (attendent toutes les features)
      ├── train_mlp
      ├── train_xgboost
      │
      ├── deploy_model           (copie les meilleurs modèles → MinIO)
      │
      └── verify_inference       (appelle l'endpoint backend)

Planning : quotidien à 06:00 UTC (après les runs d'ingestion nocturnes).

Les étapes ``build_features_*`` et ``train_*`` sont déclenchées via un
appel HTTP au conteneur ``crypto-bot-ml-api`` (routes ``/internal/pipeline/...``),
plutôt que d'exécuter ``python -m src.main`` dans l'environnement Python d'Airflow.
Raison : ml-api a déjà torch/mlflow/scikit-learn qui fonctionnent ; les installer
en plus dans l'image Airflow (qui a son propre arbre de dépendances, providers
compris) provoque des conflits de versions (ex: email-validator/pydantic requis
par Flask-AppBuilder vs. celui tiré par une version récente de mlflow). Airflow
orchestre, il n'a pas besoin d'héberger la stack ML.

Prérequis Docker (docker-compose.yml) :
    Ajouter sous ``x-airflow-common > volumes`` :
        - ./models:/opt/airflow/models
        - ./utils:/opt/airflow/utils
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/opt/airflow")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")

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

SYMBOLS = ["BTCUSDC", "ETHUSDC"]
INTERVAL = "1h"

# Dataset processed (output de build_features, input de train-rf). Chemin relatif au
# cwd de crypto-bot-ml-api (/app), PAS a MODELS_DIR (bind-mount cote Airflow) : ml-api
# execute ces routes dans son propre conteneur, dont /app/data pointe vers ./data a la
# racine du repo (cf. docker-compose.yml), pas vers ./models/data (qui n'existe pas).
PROCESSED_DIR = os.path.join("data", "processed")

INFERENCE_URL = os.environ.get(
    "INFERENCE_URL", "http://crypto-bot-backend:8009/api/v1/inference"
)
ML_API_URL = os.environ.get("ML_API_URL", "http://crypto-bot-ml-api:8010")

# Le training peut prendre plusieurs minutes sur le jeu de donnees complet.
PIPELINE_HTTP_TIMEOUT_SECONDS = 900

# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------


def _feature_path(symbol: str) -> str:
    return os.path.join(PROCESSED_DIR, symbol.upper(), f"{INTERVAL}_features.parquet")


def _build_features_callable(symbol: str) -> None:
    """Appelle POST /internal/pipeline/features sur crypto-bot-ml-api."""
    response = requests.post(
        f"{ML_API_URL}/internal/pipeline/features",
        json={"symbols": [symbol], "interval": INTERVAL, "config": "config.yaml"},
        timeout=PIPELINE_HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    logger.info("build_features %s: %s", symbol, response.json())


def _train_random_forest_callable() -> None:
    """Appelle POST /internal/pipeline/train-rf sur crypto-bot-ml-api."""
    dataset = _feature_path(SYMBOLS[0])
    response = requests.post(
        f"{ML_API_URL}/internal/pipeline/train-rf",
        json={"dataset": dataset, "config": "config.yaml"},
        timeout=PIPELINE_HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    logger.info("train_random_forest: %s", response.json())


def _train_mlp_callable() -> None:
    """Appelle POST /internal/pipeline/train-mlp sur crypto-bot-ml-api."""
    dataset = _feature_path(SYMBOLS[0])
    response = requests.post(
        f"{ML_API_URL}/internal/pipeline/train-mlp",
        json={"dataset": dataset, "config": "config.yaml"},
        timeout=PIPELINE_HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    logger.info("train_mlp: %s", response.json())


def _train_xgboost_callable() -> None:
    """Appelle POST /internal/pipeline/train-xgboost sur crypto-bot-ml-api."""
    dataset = _feature_path(SYMBOLS[0])
    response = requests.post(
        f"{ML_API_URL}/internal/pipeline/train-xgboost",
        json={"dataset": dataset, "config": "config.yaml"},
        timeout=PIPELINE_HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    logger.info("train_xgboost: %s", response.json())


def _verify_inference_callable() -> None:
    """Appelle /inference/predict avec un vrai vecteur de features (derniere ligne du
    dataset traite), pas un features factice — un vecteur incomplet echoue en 400,
    jamais en 200 (piege trouve dans la version initiale de ce DAG, jamais verifiee
    en conditions reelles avant ce diagnostic)."""
    import pandas as pd

    feature_columns = requests.get(f"{INFERENCE_URL}/model", timeout=30).json()["feature_columns"]
    dataset_path = os.path.join("/app", _feature_path(SYMBOLS[0]))
    row = pd.read_parquet(dataset_path).iloc[-1]
    features = {col: float(row[col]) for col in feature_columns}

    response = requests.post(
        f"{INFERENCE_URL}/predict",
        json={"symbol": SYMBOLS[0], "interval": INTERVAL, "features": features},
        timeout=60,
    )
    response.raise_for_status()
    logger.info("verify_inference: %s", response.json())


def _deploy_callable(model_name: str = "random_forest") -> None:
    """Appelle le job de déploiement (importé depuis jobs/).

    ``registry_root`` doit être explicite : le registre local est écrit par
    crypto-bot-ml-api sous son propre cwd (/app/artifacts/registry), ce qui
    correspond cote host a ``models/artifacts/registry``. Le defaut de
    deploy_model.py ("artifacts/registry", relatif au cwd du process Airflow)
    pointe vers un tout autre dossier -- jamais le bon.
    """
    if not _DEPLOY_AVAILABLE:
        raise RuntimeError("deploy_model.py non disponible dans jobs/")
    registry_root = Path(MODELS_DIR) / "artifacts" / "registry"
    ok = _deploy(model_name=model_name, registry_root=registry_root)
    if not ok:
        raise RuntimeError(f"Échec du déploiement du modèle {model_name}")


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
        "Pipeline ML complet : build features → entraînement Random Forest / "
        "MLP / XGBoost → déploiement des modèles vers MinIO → vérification de "
        "l'API d'inférence"
    ),
    schedule_interval="0 6 * * *",       # chaque jour à 06:00 UTC
    catchup=False,
    max_active_runs=1,
    tags=["ml", "training", "deployment", "inference"],
) as dag:

    # -- 1. Build features pour chaque symbole (appel HTTP a crypto-bot-ml-api) ---
    build_tasks = []
    for symbol in SYMBOLS:
        task = PythonOperator(
            task_id=f"build_features_{symbol}_{INTERVAL}",
            python_callable=_build_features_callable,
            op_kwargs={"symbol": symbol},
            retries=2,
            retry_delay=timedelta(minutes=2),
        )
        build_tasks.append(task)

    # -- 2. Entraînements (appels HTTP a crypto-bot-ml-api) -----------------------
    train_rf = PythonOperator(
        task_id="train_random_forest",
        python_callable=_train_random_forest_callable,
        retries=1,
        retry_delay=timedelta(minutes=5),
    )
    train_mlp = PythonOperator(
        task_id="train_mlp",
        python_callable=_train_mlp_callable,
        retries=1,
        retry_delay=timedelta(minutes=5),
    )
    train_xgboost = PythonOperator(
        task_id="train_xgboost",
        python_callable=_train_xgboost_callable,
        retries=1,
        retry_delay=timedelta(minutes=5),
    )

    # -- 3. Déploiement vers MinIO -------------------------------------------------
    deploy_rf = PythonOperator(
        task_id="deploy_model_random_forest",
        python_callable=_deploy_callable,
        op_kwargs={"model_name": "random_forest"},
    )
    deploy_mlp = PythonOperator(
        task_id="deploy_model_mlp",
        python_callable=_deploy_callable,
        op_kwargs={"model_name": "mlp"},
    )
    deploy_xgboost = PythonOperator(
        task_id="deploy_model_xgboost",
        python_callable=_deploy_callable,
        op_kwargs={"model_name": "xgboost"},
    )

    # -- 4. Vérification de l'API d'inférence -----------------------------------
    verify = PythonOperator(
        task_id="verify_inference",
        python_callable=_verify_inference_callable,
    )

    # -- Ordonnancement ---------------------------------------------------------
    # Toutes les features en parallèle → puis les entraînements (parallèles)
    # → puis les déploiements (parallèles) → puis la vérification
    for task in (train_rf, train_mlp, train_xgboost):
        task.set_upstream(build_tasks)
    deploy_rf.set_upstream(train_rf)
    deploy_mlp.set_upstream(train_mlp)
    deploy_xgboost.set_upstream(train_xgboost)
    verify.set_upstream([deploy_rf, deploy_mlp, deploy_xgboost])
