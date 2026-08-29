from __future__ import annotations

# Modeles implementes par l'app (cote entrainement models/src/training/, cote serving
# models/src/api/main.py::AVAILABLE_MODELS). Source unique de verite, meme principe que
# utils/connectors/exchanges/registry.py pour les exchanges/paires : un seul endroit a
# modifier pour ajouter un modele, plutot que des listes paralleles qui peuvent diverger.
#
# Tous les modeles ici ne sont pas forcement automatises partout : par exemple le DAG
# cryptobot_ml_pipeline (orchestration/dags/ml_pipeline.py) n'en entraine actuellement
# qu'un sous-ensemble explicite (TRAINABLE_MODELS), filtre depuis cette liste -- pas une
# liste independante -- pour qu'un modele renomme/retire ici se repercute partout.
SUPPORTED_MODELS = ["random_forest", "xgboost", "mlp", "lstm"]

# Sous-ensemble de SUPPORTED_MODELS entraine par paire et enregistre dans le MLflow Model
# Registry sous un nom qualifie "<model_name>_<symbol>" (cf. models/src/training/
# train_random_forest.py, train_xgboost.py, train_mlp.py). LSTM reste hors de ce
# sous-ensemble tant qu'il n'a pas de route HTTP d'entrainement cote ml-api -- source
# unique de verite pour ml_pipeline.py (TRAINABLE_MODELS) et pour
# BotMlClient.list_trained_combos() (backend/src/bots/ml_client.py).
PAIR_QUALIFIED_MODELS = ["random_forest", "xgboost", "mlp"]


def list_configured_models() -> list[str]:
    """Modeles ML implementes par l'app."""
    return list(SUPPORTED_MODELS)


def list_pair_qualified_models() -> list[str]:
    """Modeles entraines par paire (enregistres sous "<model>_<symbol>" dans MLflow)."""
    return [model for model in SUPPORTED_MODELS if model in PAIR_QUALIFIED_MODELS]
