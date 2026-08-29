"""DAG ML Pipeline : features → training → déploiement → vérification.

Enchaîne les étapes du pipeline ML après que les données brutes ont été
ingérées par le DAG ``ingest_ohlcv_binance_to_minio``. Le graphe exact (nombre
de tâches d'entraînement/déploiement) dépend de SYMBOLS (source unique de
vérité : utils.connectors.exchanges.registry.list_configured_symbols()) et de
TRAINABLE_MODELS ci-dessous -- pas de liste figée dans cette docstring, elle
se périmerait au premier ajout de paire ou de modèle :

    start
      ├── build_features_<symbol>_<interval>   (un par couple symbole x interval,
      │                                          cf. SYMBOLS x INTERVALS)
      │
      ├── train_<model>_<symbol>_<interval>    (un par triplet modèle x symbole x
      │                                          interval, cf. TRAINABLE_MODELS x
      │                                          SYMBOLS x INTERVALS)
      │
      ├── deploy_model_<model>              (un par modèle, copie vers MinIO,
      │                                       chemin A inchangé)
      │
      ├── verify_inference                  (appelle l'endpoint ml-api)
      │
      └── sync_bot_templates                (appelle POST /internal/bot-templates/sync
                                               sur crypto-bot-backend, chemin B : rend
                                               les modèles fraîchement entraînés visibles
                                               dans le catalogue sans attendre un
                                               redémarrage du backend)

RF, XGBoost et MLP sont en plus enregistrés dans le MLflow Model Registry sous
un nom qualifié par paire ("random_forest_btcusdc", "mlp_ethusdc", ...) :
c'est ce registre que le module bots/ interroge pour exécuter un bot
(BotMlClient.predict()), par opposition au registre local ci-dessus
(chemin A, un seul emplacement par type de modèle, utilisé par
/signals/latest et l'ancien module strategy/).

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

from utils.connectors.exchanges.registry import list_configured_symbols
from utils.ml.registry import list_pair_qualified_models

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

# Source unique de verite (utils/connectors/exchanges/registry.py) -- plus de liste
# dupliquee ici. Ajouter une paire cote app (utils) suffit a l'entrainer, aucune autre
# modification necessaire dans ce DAG.
SYMBOLS = list_configured_symbols()

# A garder synchronise manuellement avec models/config.yaml::data.intervals (mlflow_registry.
# list_trained_combos() n'y fait apparaitre un combo entraine ici que si son interval y figure
# aussi) -- pas de source unique automatique, Airflow n'importe pas la stack ML (cf. docstring
# module plus haut) donc ce DAG ne peut pas lire config.yaml directement sans web de deps.
# 1m/5m entraines en plus du 1h pour avoir des signaux/trades plus frequents en demo -- le
# backfill correspondant (bien plus volumineux, cf. backfill_ohlcv_*) doit avoir ete fait au
# prealable, sinon build_features echoue faute de donnees brutes a cet interval.
INTERVALS = ["1h", "5m", "1d"]

# Modeles entraines sur le chemin B (MLflow Model Registry, nom qualifie par paire,
# interroge par bots/ via BotMlClient.predict()). Convention stricte cote ml-api : la
# route d'entrainement d'un modele "X" est toujours POST /internal/pipeline/train-X
# (cf. models/src/api/main.py) -- pas de mapping a maintenir a la main ici, juste le nom
# du modele.
#
# TRAINABLE_MODELS reprend utils.ml.registry.list_pair_qualified_models() (source unique
# de verite pour "quels modeles sont entraines par paire", partagee avec
# BotMlClient.list_trained_combos() cote backend) : un modele retire/renomme cote utils
# disparait automatiquement d'ici. LSTM pas encore automatise dans ce DAG (pas de route
# HTTP d'entrainement cote ml-api) ; propose en perspective d'amelioration pour la
# soutenance. RF, XGBoost et MLP sont tous les trois qualifies par paire (chemin B).
TRAINABLE_MODELS = list_pair_qualified_models()

# Dataset processed (output de build_features, input de train-rf). Chemin relatif au
# cwd de crypto-bot-ml-api (/app), PAS a MODELS_DIR (bind-mount cote Airflow) : ml-api
# execute ces routes dans son propre conteneur, dont /app/data pointe vers ./data a la
# racine du repo (cf. docker-compose.yml), pas vers ./models/data (qui n'existe pas).
PROCESSED_DIR = os.path.join("data", "processed")

ML_API_URL = os.environ.get("ML_API_URL", "http://crypto-bot-ml-api:8010")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://crypto-bot-backend:8009")

# Le training peut prendre plusieurs minutes sur le jeu de donnees complet.
PIPELINE_HTTP_TIMEOUT_SECONDS = 900

# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------


def _feature_path(symbol: str, interval: str) -> str:
    return os.path.join(PROCESSED_DIR, symbol.upper(), f"{interval}_features.parquet")


def _build_features_callable(symbol: str, interval: str) -> None:
    """Appelle POST /internal/pipeline/features sur crypto-bot-ml-api."""
    response = requests.post(
        f"{ML_API_URL}/internal/pipeline/features",
        json={"symbols": [symbol], "interval": interval, "config": "config.yaml"},
        timeout=PIPELINE_HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    logger.info("build_features %s %s: %s", symbol, interval, response.json())


def _train_model_callable(model_name: str, symbol: str, interval: str) -> None:
    """Appelle POST /internal/pipeline/train-<model_name> sur crypto-bot-ml-api.

    Un appel par triplet modele x symbole x interval (cf. TRAINABLE_MODELS x SYMBOLS x
    INTERVALS dans la configuration du DAG) : chaque triplet est enregistre dans le
    MLflow Model Registry sous un nom qualifie ("<model_name>_<symbol>_<interval>"),
    sinon un triplet entraine en second ecraserait le premier au meme nom.
    """
    dataset = _feature_path(symbol, interval)
    url = f"{ML_API_URL}/internal/pipeline/train-{model_name}"
    response = requests.post(
        url,
        json={"dataset": dataset, "config": "config.yaml", "symbol": symbol, "interval": interval},
        timeout=PIPELINE_HTTP_TIMEOUT_SECONDS,
    )
    if response.status_code == 404:
        raise RuntimeError(
            f"Route d'entrainement introuvable: {url}. TRAINABLE_MODELS contient "
            f"'{model_name}' mais aucune route POST /internal/pipeline/train-{model_name} "
            f"n'existe cote ml-api (models/src/api/main.py) -- verifier la convention de "
            f"nommage ou ajouter la route manquante."
        )
    response.raise_for_status()
    logger.info("train_%s %s %s: %s", model_name, symbol, interval, response.json())


def _verify_inference_callable() -> None:
    """Verifie le pipeline d'inference cote ml-api.

    Appelle GET /signals/latest sur crypto-bot-ml-api : cette route construit
    elle-meme les features depuis MinIO (via build_symbol_features) et sert une
    prediction avec le modele deployee, le tout cote serveur. C'est un veritable
    aller-retour data -> features -> modele, sans dependre du filesystem local
    d'Airflow (l'ancienne version lisait le parquet de features dans le conteneur
    Airflow, chemin qui n'existe pas en staging/production ou ml-api tourne dans
    un conteneur separe avec son propre /app/data).
    """
    response = requests.get(
        f"{ML_API_URL}/signals/latest",
        params={"symbol": SYMBOLS[0], "interval": INTERVALS[0], "model": "random_forest"},
        timeout=60,
    )
    response.raise_for_status()
    body = response.json()
    logger.info("verify_inference signal=%s confidence=%s model=%s", body["signal"], body["confidence"], body["model_name"])


def _sync_bot_templates_callable() -> None:
    """Appelle POST /internal/bot-templates/sync sur crypto-bot-backend.

    Le backend ne resynchronise sinon les templates ML (BotService.
    sync_builtin_templates(), chemin B) qu'a son propre demarrage (cf.
    lifespan() dans backend/src/main.py) : si celui-ci a lieu avant que ce DAG
    n'ait entraine/enregistre les modeles dans le MLflow Model Registry
    (typiquement au premier deploiement, backend et Airflow demarrant en
    parallele), le catalogue reste vide jusqu'a un redemarrage manuel. Cet
    appel ferme la boucle : le catalogue est a jour des la fin du pipeline,
    sans dependre de l'ordre de demarrage des conteneurs.
    """
    response = requests.post(f"{BACKEND_URL}/internal/bot-templates/sync", timeout=60)
    response.raise_for_status()
    logger.info("sync_bot_templates: %s", response.json())


def _deploy_callable(model_name: str) -> None:
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

    # -- 1. Build features pour chaque couple (symbole, interval) (appel HTTP a crypto-bot-ml-api) --
    build_tasks_by_symbol_interval = {}
    for symbol in SYMBOLS:
        for interval in INTERVALS:
            build_tasks_by_symbol_interval[(symbol, interval)] = PythonOperator(
                task_id=f"build_features_{symbol}_{interval}",
                python_callable=_build_features_callable,
                op_kwargs={"symbol": symbol, "interval": interval},
                retries=2,
                retry_delay=timedelta(minutes=2),
            )

    # -- 2. Entraînements (appels HTTP a crypto-bot-ml-api) -----------------------
    # Une tache par triplet (modele, symbole, interval) dans TRAINABLE_MODELS x SYMBOLS x
    # INTERVALS -- ajouter une paire (utils), un modele (TRAINABLE_MODELS) ou un interval
    # (INTERVALS ci-dessus) suffit, aucune duplication de code.
    train_tasks_by_model = {model_name: {} for model_name in TRAINABLE_MODELS}
    for model_name in TRAINABLE_MODELS:
        for symbol in SYMBOLS:
            for interval in INTERVALS:
                task = PythonOperator(
                    task_id=f"train_{model_name}_{symbol}_{interval}",
                    python_callable=_train_model_callable,
                    op_kwargs={"model_name": model_name, "symbol": symbol, "interval": interval},
                    retries=1,
                    retry_delay=timedelta(minutes=5),
                )
                task.set_upstream(build_tasks_by_symbol_interval[(symbol, interval)])
                train_tasks_by_model[model_name][(symbol, interval)] = task

    # -- 3. Déploiement vers MinIO (chemin A, un emplacement par modele, inchangé) --
    deploy_tasks_by_model = {}
    for model_name in TRAINABLE_MODELS:
        deploy_task = PythonOperator(
            task_id=f"deploy_model_{model_name}",
            python_callable=_deploy_callable,
            op_kwargs={"model_name": model_name},
        )
        deploy_task.set_upstream(list(train_tasks_by_model[model_name].values()))
        deploy_tasks_by_model[model_name] = deploy_task

    # -- 4. Vérification de l'API d'inférence -----------------------------------
    verify = PythonOperator(
        task_id="verify_inference",
        python_callable=_verify_inference_callable,
    )
    verify.set_upstream(list(deploy_tasks_by_model.values()))

    # -- 5. Resynchronisation du catalogue de bots cote backend ------------------
    sync_bot_templates = PythonOperator(
        task_id="sync_bot_templates",
        python_callable=_sync_bot_templates_callable,
        retries=2,
        retry_delay=timedelta(minutes=2),
    )
    sync_bot_templates.set_upstream(list(deploy_tasks_by_model.values()))
