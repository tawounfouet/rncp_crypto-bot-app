"""Train the LSTM classifier."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config.config_loader import load_config
from src.data.storage import read_dataset
from src.mlops.model_card import write_model_card
from src.mlops.registry import register_best_model
from src.mlops.tracking import new_run_id, start_run
from src.models.lstm import save_lstm_artifacts, train_lstm
from src.utils.logger import get_logger


logger = get_logger(__name__)


def train_from_processed_dataset(path: str | Path, config_path: str = "config.yaml") -> Path:
    """Train LSTM from a processed dataset path and return artifact directory."""
    settings = load_config(config_path)
    logger.info("train_lstm job start dataset=%s config=%s", path, config_path)
    data = read_dataset(path)
    run_id = new_run_id(settings)
    logger.info("train_lstm run created run_id=%s rows=%s", run_id, len(data))
    result = train_lstm(data, settings)
    artifact_dir = Path(settings.data.paths.artifacts) / "lstm" / run_id
    save_lstm_artifacts(result, artifact_dir)
    write_model_card(
        artifact_dir,
        model_name="lstm",
        run_id=run_id,
        metrics=result["metrics"],
        dataset_summary={
            "rows": len(data),
            "source": str(path),
            "sequence_length": result["model_config"]["sequence_length"],
            "test_sequences": result["test_rows"],
        },
    )
    with start_run(settings, "lstm", run_id=run_id) as run:
        run.log_params({**settings.models.lstm.model_dump(), **settings.training.model_dump()})
        run.log_metrics(result["metrics"])
        run.log_artifacts(artifact_dir)
    if settings.mlops.register_best_model:
        registry_path = register_best_model(artifact_dir, settings.mlops.model_registry_path, "lstm")
        logger.info("train_lstm registry updated path=%s", registry_path)
    logger.info("train_lstm job complete artifact_dir=%s metrics=%s", artifact_dir, result["metrics"])
    return artifact_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Train LSTM classifier.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()
    train_from_processed_dataset(args.dataset, args.config)


if __name__ == "__main__":
    main()
