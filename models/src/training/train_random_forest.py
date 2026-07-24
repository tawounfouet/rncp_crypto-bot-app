"""Train the Random Forest baseline."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.config.config_loader import load_config
from src.data.storage import read_dataset
from src.mlops.model_card import write_model_card
from src.mlops.registry import register_best_model
from src.mlops.tracking import new_run_id, start_run
from src.models.random_forest import save_random_forest_artifacts, train_random_forest
from src.utils.logger import get_logger


logger = get_logger(__name__)


def train_from_processed_dataset(path: str | Path, config_path: str = "config.yaml") -> Path:
    """Train RF from a processed dataset path and return artifact directory."""
    settings = load_config(config_path)
    logger.info("train_random_forest job start dataset=%s config=%s", path, config_path)
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
        dataset_summary={"rows": len(data), "source": str(path)},
    )
    with start_run(settings, "random_forest", run_id=run_id) as run:
        run.log_params(settings.models.random_forest.model_dump())
        run.log_metrics(result["metrics"])
        run.log_artifacts(artifact_dir)
    if settings.mlops.register_best_model:
        registry_path = register_best_model(artifact_dir, settings.mlops.model_registry_path, "random_forest")
        logger.info("train_random_forest registry updated path=%s", registry_path)
    logger.info("train_random_forest job complete artifact_dir=%s metrics=%s", artifact_dir, result["metrics"])
    return artifact_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Random Forest baseline.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()
    train_from_processed_dataset(args.dataset, args.config)


if __name__ == "__main__":
    main()
