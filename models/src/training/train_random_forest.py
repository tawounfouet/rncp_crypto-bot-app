"""Train the Random Forest baseline."""

from __future__ import annotations

import argparse
from pathlib import Path

import mlflow.sklearn
from sklearn.pipeline import Pipeline

from src.config.config_loader import load_config
from src.data.storage import read_dataset
from src.mlops.model_card import write_model_card
from src.mlops.registry import register_best_model
from src.mlops.tracking import new_run_id, start_run
from src.models.random_forest import save_random_forest_artifacts, train_random_forest
from src.utils.logger import get_logger


logger = get_logger(__name__)


def train_from_processed_dataset(path: str | Path, config_path: str = "config.yaml", *, symbol: str) -> Path:
    """Train RF from a processed dataset path and return artifact directory.

    Enregistre aussi le couple scaler+modele comme un seul sklearn.Pipeline dans le
    MLflow Model Registry, sous un nom qualifie par paire (ex. "random_forest_btcusdc") --
    c'est ce registre que bots/service.py interroge via BotMlClient.predict(), pas le
    registre local (registry.py/register_best_model, laisse inchange ici). Un Pipeline et
    non le RandomForestClassifier seul : le modele a appris ses seuils de decision sur des
    features mises a l'echelle par le scaler, pas sur les features brutes que
    predict_registered_bot_model() transmet telles quelles.
    """
    settings = load_config(config_path)
    logger.info("train_random_forest job start dataset=%s config=%s symbol=%s", path, config_path, symbol)
    data = read_dataset(path)
    run_id = new_run_id(settings)
    logger.info("train_random_forest run created run_id=%s rows=%s", run_id, len(data))
    result = train_random_forest(data, settings)
    artifact_dir = Path(settings.data.paths.artifacts) / "random_forest" / run_id
    save_random_forest_artifacts(result, artifact_dir)
    write_model_card(
        artifact_dir,
        model_name="random_forest",
        run_id=run_id,
        metrics=result["metrics"],
        dataset_summary={"rows": len(data), "source": str(path), "symbol": symbol.upper()},
    )
    registered_model_name = f"random_forest_{symbol.lower()}"
    with start_run(settings, "random_forest", run_id=run_id, symbol=symbol) as run:
        run.log_params(settings.models.random_forest.model_dump())
        run.log_metrics(result["metrics"])
        run.log_artifacts(artifact_dir)
        pipeline = Pipeline([("scaler", result["scaler"]), ("model", result["model"])])
        mlflow.sklearn.log_model(
            pipeline,
            "model",
            registered_model_name=registered_model_name,
            # cloudpickle plutot que le defaut skops : uniforme avec train_xgboost.py (skops
            # refuse XGBClassifier comme type "non fiable", cf. commentaire la-bas).
            serialization_format=mlflow.sklearn.SERIALIZATION_FORMAT_CLOUDPICKLE,
        )
        logger.info("train_random_forest registered in MLflow Model Registry name=%s", registered_model_name)
    if settings.mlops.register_best_model:
        registry_path = register_best_model(artifact_dir, settings.mlops.model_registry_path, "random_forest")
        logger.info("train_random_forest registry updated path=%s", registry_path)
    logger.info("train_random_forest job complete artifact_dir=%s metrics=%s", artifact_dir, result["metrics"])
    return artifact_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Random Forest baseline.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--symbol", required=True)
    args = parser.parse_args()
    train_from_processed_dataset(args.dataset, args.config, symbol=args.symbol)


if __name__ == "__main__":
    main()
