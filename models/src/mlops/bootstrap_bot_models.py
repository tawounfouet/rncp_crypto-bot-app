"""Bootstrap bot-specific MLflow models for local development."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import mlflow
from mlflow.tracking import MlflowClient

from src.config.config_loader import load_config
from src.training.train_bot_rsi_reversal import BOT_RSI_REVERSAL_MODEL_NAME, train_from_processed_dataset


def _configure_tracking(config_path: str) -> None:
    settings = load_config(config_path)
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI") or settings.mlops.tracking_uri)


def registered_versions(model_name: str, config_path: str = "config.yaml") -> list[str]:
    _configure_tracking(config_path)
    client = MlflowClient()
    return [str(version.version) for version in client.search_model_versions(f"name='{model_name}'")]


def ensure_bot_rsi_reversal_model(config_path: str = "config.yaml", *, force: bool = False) -> dict[str, str]:
    versions = registered_versions(BOT_RSI_REVERSAL_MODEL_NAME, config_path)
    if versions and not force:
        latest = max(versions, key=lambda version: int(version))
        return {
            "model_name": BOT_RSI_REVERSAL_MODEL_NAME,
            "model_version": latest,
            "status": "already_registered",
        }

    result = train_from_processed_dataset(
        Path("data/processed/BTCUSDT/1h_features.parquet"),
        config_path,
        registered_model_name=BOT_RSI_REVERSAL_MODEL_NAME,
    )
    return {
        "model_name": str(result["model_name"]),
        "model_version": str(result["model_version"]),
        "status": "registered",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure bot MLflow models exist for development.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--force", action="store_true", help="Create a new version even if one exists")
    args = parser.parse_args()
    result = ensure_bot_rsi_reversal_model(args.config, force=args.force)
    print(
        "bot_rsi_reversal artifact ready: "
        f"name={result['model_name']} version={result['model_version']} status={result['status']}"
    )


if __name__ == "__main__":
    main()
