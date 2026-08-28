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


def list_configured_models() -> list[str]:
    """Modeles ML implementes par l'app."""
    return list(SUPPORTED_MODELS)
