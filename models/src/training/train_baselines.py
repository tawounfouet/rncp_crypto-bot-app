"""Evaluate AlwaysHold and UniformRandom baselines and track them in mlruns."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from src.config.config_loader import load_config
from src.data.storage import read_dataset
from src.mlops.tracking import new_run_id, start_run
from src.models.baselines import AlwaysHoldClassifier, UniformRandomClassifier, evaluate_baseline
from src.models.lstm import temporal_split
from src.utils.logger import get_logger


logger = get_logger(__name__)

_CV_SKIP_ROWS = 5000


def train_from_processed_dataset(path: str | Path, config_path: str = "config.yaml") -> None:
    """Evaluate baselines on the test split of path and record in mlruns."""
    settings = load_config(config_path)
    logger.info("train_baselines job start dataset=%s config=%s", path, config_path)

    data = read_dataset(path)
    _, _, test = temporal_split(data, settings)
    label_names = [settings.id_to_label[i] for i in sorted(settings.id_to_label)]
    y_test = test["target"].to_numpy()

    baselines = [
        ("always_hold", AlwaysHoldClassifier(hold_label="HOLD")),
        ("random_classifier", UniformRandomClassifier(labels=label_names, random_state=settings.project.random_state)),
    ]

    for name, clf in baselines:
        y_pred = clf.predict(np.empty(len(y_test)))
        metrics = evaluate_baseline(name, y_test, y_pred, label_names)
        run_id = new_run_id(settings)
        with start_run(settings, name, run_id=run_id) as run:
            run.log_params({"model": name, "test_rows": len(y_test)})
            run.log_metrics(metrics)
        logger.info("train_baselines %s run_id=%s metrics=%s", name, run_id, metrics)

    logger.info("train_baselines job complete dataset=%s", path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate baseline classifiers.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dataset", default="data/processed/BTCUSDT/1h_features.parquet")
    args = parser.parse_args()
    train_from_processed_dataset(args.dataset, args.config)


if __name__ == "__main__":
    main()
