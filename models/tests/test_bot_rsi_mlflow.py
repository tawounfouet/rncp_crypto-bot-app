from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11) or importlib.util.find_spec("mlflow") is None,
    reason="Python 3.11+ and mlflow are required for MLflow registry tests",
)


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"


def _tracking_uri(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def test_train_registers_new_mlflow_model_versions(tmp_path, monkeypatch):
    import mlflow

    from src.mlops.bootstrap_dev_artifacts import build_feature_frame
    from src.training.train_bot_rsi_reversal import BOT_RSI_REVERSAL_MODEL_NAME, train_from_processed_dataset

    tracking_db = tmp_path / "mlflow.db"
    artifact_root = tmp_path / "artifacts"
    dataset_path = tmp_path / "btc_features.csv"
    build_feature_frame("BTCUSDT", rows=220).to_csv(dataset_path, index=False)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", _tracking_uri(tracking_db))
    monkeypatch.setenv("MLFLOW_ARTIFACT_ROOT", artifact_root.as_posix())

    first = train_from_processed_dataset(dataset_path, str(CONFIG_PATH))
    second = train_from_processed_dataset(dataset_path, str(CONFIG_PATH))

    assert first["model_name"] == BOT_RSI_REVERSAL_MODEL_NAME
    assert int(second["model_version"]) > int(first["model_version"])
    client = mlflow.tracking.MlflowClient()
    versions = client.search_model_versions(f"name='{BOT_RSI_REVERSAL_MODEL_NAME}'")
    assert len(versions) >= 2


def test_registered_mlflow_model_can_be_loaded_for_prediction(tmp_path, monkeypatch):
    from src.inference.mlflow_registry import predict_registered_bot_model
    from src.mlops.bootstrap_dev_artifacts import build_feature_frame
    from src.training.train_bot_rsi_reversal import (
        BOT_RSI_REVERSAL_FEATURES,
        BOT_RSI_REVERSAL_MODEL_NAME,
        train_from_processed_dataset,
    )

    tracking_db = tmp_path / "mlflow.db"
    artifact_root = tmp_path / "artifacts"
    dataset_path = tmp_path / "btc_features.csv"
    build_feature_frame("BTCUSDT", rows=220).to_csv(dataset_path, index=False)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", _tracking_uri(tracking_db))
    monkeypatch.setenv("MLFLOW_ARTIFACT_ROOT", artifact_root.as_posix())
    result = train_from_processed_dataset(dataset_path, str(CONFIG_PATH))

    features = {name: 1.0 for name in BOT_RSI_REVERSAL_FEATURES}
    features.update({"rsi": 42.0, "price_change": 0.001, "volume": 120.0, "sma_short": 65000.0, "sma_long": 64800.0})
    prediction = predict_registered_bot_model(
        model_name=BOT_RSI_REVERSAL_MODEL_NAME,
        model_version=result["model_version"],
        features=features,
        config_path=str(CONFIG_PATH),
    )

    assert prediction["model_source"] == "mlflow"
    assert prediction["model_version"] == result["model_version"]
    assert prediction["signal"] in {"BUY", "SELL", "HOLD"}
    assert 0 <= prediction["confidence"] <= 1
