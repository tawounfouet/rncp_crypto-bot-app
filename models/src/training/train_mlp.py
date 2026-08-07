"""Train the MLP baseline."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config.config_loader import load_config
from src.data.storage import read_dataset
from src.mlops.model_card import write_model_card
from src.mlops.registry import register_best_model
from src.mlops.tracking import new_run_id, start_run
from src.models.mlp import save_mlp_artifacts, train_mlp
from src.utils.logger import get_logger


logger = get_logger(__name__)


def train_from_processed_dataset(path: str | Path, config_path: str = "config.yaml") -> Path:
    """Train MLP from a processed dataset path and return artifact directory."""
    settings = load_config(config_path)
    logger.info("train_mlp job start dataset=%s config=%s", path, config_path)
    data = read_dataset(path)
    run_id = new_run_id(settings)
    logger.info("train_mlp run created run_id=%s rows=%s", run_id, len(data))
    result = train_mlp(data, settings)
    artifact_dir = Path(settings.data.paths.artifacts) / "mlp" / run_id
    save_mlp_artifacts(result, artifact_dir)
    write_model_card(
        artifact_dir,
        model_name="mlp",
        run_id=run_id,
        metrics=result["metrics"],
        dataset_summary={"rows": len(data), "source": str(path)},
    )
    with start_run(settings, "mlp", run_id=run_id) as run:
        run.log_params(settings.models.mlp.model_dump())
        run.log_metrics(result["metrics"])
        run.log_artifacts(artifact_dir)
    if settings.mlops.register_best_model:
        registry_path = register_best_model(artifact_dir, settings.mlops.model_registry_path, "mlp")
        logger.info("train_mlp registry updated path=%s", registry_path)
    logger.info("train_mlp job complete artifact_dir=%s metrics=%s", artifact_dir, result["metrics"])
    return artifact_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Train MLP baseline.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()
    train_from_processed_dataset(args.dataset, args.config)


if __name__ == "__main__":
    main()
