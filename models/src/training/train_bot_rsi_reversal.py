"""Train the first bot-specific MLflow model for BTCUSDC 1h RSI reversal.

Le nom du modele enregistre (BOT_RSI_REVERSAL_MODEL_NAME) reste "..._btcusdt_1h" pour
matcher le modele deja enregistre dans le registre MLflow (entraine sur BTCUSDT avant la
migration de conformite MiCA, commit e2455de) -- seul le symbole/dataset par defaut de ce
script a ete corrige vers BTCUSDC, prets pour un reentrainement quand celui-ci sera lance."""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.tracking import MlflowClient
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

from src.config.config_loader import load_config
from src.data.storage import read_dataset
from src.mlops.bootstrap_dev_artifacts import build_feature_frame
from src.utils.logger import get_logger


logger = get_logger(__name__)

BOT_RSI_REVERSAL_MODEL_NAME = "bot_rsi_reversal_btcusdt_1h"
BOT_RSI_REVERSAL_FEATURES = ["rsi", "price_change", "volume", "sma_short", "sma_long"]
BOT_LABELS = ["BUY", "SELL", "HOLD"]


def _tracking_uri(settings: Any, tracking_uri: str | None = None) -> str:
    return tracking_uri or os.getenv("MLFLOW_TRACKING_URI") or settings.mlops.tracking_uri


def _artifact_root(settings: Any, artifact_root: str | None = None) -> str:
    return artifact_root or os.getenv("MLFLOW_ARTIFACT_ROOT") or str(Path(settings.data.paths.artifacts) / "mlflow")


def _ensure_experiment(settings: Any, *, tracking_uri: str | None = None, artifact_root: str | None = None) -> None:
    mlflow.set_tracking_uri(_tracking_uri(settings, tracking_uri))
    client = MlflowClient()
    experiment = client.get_experiment_by_name(settings.mlops.experiment_name)
    root = _artifact_root(settings, artifact_root)
    if "://" not in root:
        Path(root).mkdir(parents=True, exist_ok=True)
    if experiment is None:
        client.create_experiment(settings.mlops.experiment_name, artifact_location=root)
    mlflow.set_experiment(settings.mlops.experiment_name)


def _dataset_hash(frame: pd.DataFrame) -> str:
    hashed = pd.util.hash_pandas_object(frame, index=True)
    return str(int(hashed.sum()))


def _normalise_target(data: pd.DataFrame) -> pd.Series:
    if "target" in data.columns:
        target = data["target"]
        if pd.api.types.is_numeric_dtype(target):
            mapping = {0: "SELL", 1: "HOLD", 2: "BUY"}
            return target.map(mapping).fillna("HOLD").astype(str).str.upper()
        return target.astype(str).str.upper()

    future_return = data["close"].shift(-1) / data["close"] - 1
    output = pd.Series("HOLD", index=data.index, dtype=object)
    output.loc[future_return > 0.002] = "BUY"
    output.loc[future_return < -0.002] = "SELL"
    return output


def normalise_bot_training_frame(data: pd.DataFrame) -> pd.DataFrame:
    """Return the exact V1 feature schema and BUY/SELL/HOLD target."""
    output = data.copy()
    if "rsi" not in output.columns:
        output["rsi"] = output["rsi_14"] if "rsi_14" in output.columns else _rsi(output["close"], 14)
    if "price_change" not in output.columns:
        output["price_change"] = output["return_1"] if "return_1" in output.columns else output["close"].pct_change()
    if "sma_short" not in output.columns:
        output["sma_short"] = output["sma_20"] if "sma_20" in output.columns else output["close"].rolling(10).mean()
    if "sma_long" not in output.columns:
        output["sma_long"] = output["sma_50"] if "sma_50" in output.columns else output["close"].rolling(30).mean()
    output["target"] = _normalise_target(output)
    required = [*BOT_RSI_REVERSAL_FEATURES, "target"]
    output = output[required].replace([float("inf"), float("-inf")], pd.NA).dropna().reset_index(drop=True)
    output = output[output["target"].isin(BOT_LABELS)].reset_index(drop=True)
    if output["target"].nunique() < 2:
        raise ValueError("Training dataset must contain at least two signal classes")
    return output


def _rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean().replace(0, 1e-9)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _default_dataset_path(settings: Any) -> Path:
    """Chemin du dataset par defaut, derive de la config (settings.data.symbols[0] /
    primary_interval) -- jamais un symbole en dur ici, meme motif que
    src/api/main.py::default_features_path()."""
    symbol = settings.data.symbols[0]
    interval = settings.data.primary_interval
    return (
        Path(settings.data.paths.processed)
        / symbol.upper()
        / f"{interval}_features.{settings.data.formats.processed_primary}"
    )


def load_training_frame(dataset_path: str | Path | None, settings: Any) -> tuple[pd.DataFrame, dict[str, Any]]:
    symbol = settings.data.symbols[0]
    path = Path(dataset_path) if dataset_path else _default_dataset_path(settings)
    if path.exists():
        raw = read_dataset(path)
        source = str(path)
        synthetic = False
    else:
        raw = build_feature_frame(symbol, rows=320)
        source = f"synthetic_bootstrap:{path}"
        synthetic = True
    frame = normalise_bot_training_frame(raw)
    metadata = {
        "source": source,
        "rows_raw": len(raw),
        "rows_training": len(frame),
        "columns": list(raw.columns),
        "feature_columns": BOT_RSI_REVERSAL_FEATURES,
        "target_column": "target",
        "dataset_hash": _dataset_hash(frame),
        "synthetic": synthetic,
    }
    return frame, metadata


def _train_test_split(
    frame: pd.DataFrame, train_ratio: float = 0.8
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    split_index = max(1, min(len(frame) - 1, int(len(frame) * train_ratio)))
    train = frame.iloc[:split_index]
    test = frame.iloc[split_index:]
    return (
        train[BOT_RSI_REVERSAL_FEATURES],
        test[BOT_RSI_REVERSAL_FEATURES],
        train["target"],
        test["target"],
    )


def _latest_registered_version(model_name: str, run_id: str) -> str:
    client = MlflowClient()
    versions = client.search_model_versions(f"name='{model_name}'")
    matching = [version for version in versions if version.run_id == run_id]
    if matching:
        return str(max(matching, key=lambda item: int(item.version)).version)
    if versions:
        return str(max(versions, key=lambda item: int(item.version)).version)
    return "unknown"


def train_from_processed_dataset(
    dataset_path: str | Path | None = None,
    config_path: str = "config.yaml",
    *,
    registered_model_name: str = BOT_RSI_REVERSAL_MODEL_NAME,
    tracking_uri: str | None = None,
    artifact_root: str | None = None,
) -> dict[str, Any]:
    settings = load_config(config_path)
    _ensure_experiment(settings, tracking_uri=tracking_uri, artifact_root=artifact_root)
    frame, dataset_metadata = load_training_frame(dataset_path, settings)
    x_train, x_test, y_train, y_test = _train_test_split(frame)

    model_params = {
        "model_family": "RandomForestClassifier",
        "n_estimators": 120,
        "max_depth": 6,
        "min_samples_leaf": 5,
        "class_weight": "balanced",
        "random_state": int(settings.project.random_state),
    }
    classifier = RandomForestClassifier(**{k: v for k, v in model_params.items() if k != "model_family"})
    classifier.fit(x_train, y_train)
    predictions = classifier.predict(x_test)

    metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision_macro": float(
            precision_score(y_test, predictions, labels=BOT_LABELS, average="macro", zero_division=0)
        ),
        "recall_macro": float(recall_score(y_test, predictions, labels=BOT_LABELS, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_test, predictions, labels=BOT_LABELS, average="macro", zero_division=0)),
    }
    matrix = confusion_matrix(y_test, predictions, labels=BOT_LABELS)
    training_date = datetime.now(UTC).isoformat()

    with mlflow.start_run(run_name=f"{registered_model_name}/{training_date}") as active_run:
        run_id = active_run.info.run_id
        mlflow.set_tags(
            {
                "bot_model": "true",
                "bot_slug": "ai-rsi-btcusdt-1h-v1",
                "symbol": settings.data.symbols[0],
                "timeframe": "1h",
                "strategy_type": "rsi_reversal",
                "model_registry_name": registered_model_name,
                "training_date": training_date,
            }
        )
        mlflow.log_params({**model_params, "features": ",".join(BOT_RSI_REVERSAL_FEATURES)})
        mlflow.log_metrics(metrics)
        mlflow.log_dict(dataset_metadata, "dataset.json")
        mlflow.log_dict({"features": BOT_RSI_REVERSAL_FEATURES}, "features.json")
        mlflow.log_dict(
            {"labels": BOT_LABELS, "matrix": matrix.tolist()},
            "confusion_matrix.json",
        )
        mlflow.log_dict(
            {
                "trained_at": training_date,
                "model_name": registered_model_name,
                "train_rows": len(x_train),
                "test_rows": len(x_test),
                "metrics": metrics,
            },
            "training_info.json",
        )
        model_info = mlflow.sklearn.log_model(
            sk_model=classifier,
            artifact_path="model",
            registered_model_name=registered_model_name,
            input_example=x_train.head(2),
        )

    model_version = getattr(model_info, "registered_model_version", None) or _latest_registered_version(
        registered_model_name,
        run_id,
    )
    result = {
        "model_name": registered_model_name,
        "model_version": str(model_version),
        "run_id": run_id,
        "dataset": dataset_metadata,
        "metrics": metrics,
        "trained_at": training_date,
    }
    logger.info("bot_rsi_reversal training complete result=%s", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train RSI reversal bot model in MLflow (config.yaml:data.symbols[0])."
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument(
        "--dataset",
        default=None,
        help="Processed feature dataset path (defaut : derive de config.yaml:data.symbols[0]/primary_interval)",
    )
    parser.add_argument("--model-name", default=BOT_RSI_REVERSAL_MODEL_NAME)
    args = parser.parse_args()
    result = train_from_processed_dataset(args.dataset, args.config, registered_model_name=args.model_name)
    print(
        f"bot model registered: name={result['model_name']} version={result['model_version']} run_id={result['run_id']}"
    )


if __name__ == "__main__":
    main()
