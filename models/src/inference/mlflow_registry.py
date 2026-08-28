"""Inference helpers for bot-specific models stored in MLflow Model Registry."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import mlflow
import mlflow.artifacts
import mlflow.sklearn
import pandas as pd
from mlflow.tracking import MlflowClient

from src.config.config_loader import load_config

from utils.connectors.exchanges.registry import list_configured_symbols
from utils.ml.registry import list_pair_qualified_models


class ModelUnavailable(RuntimeError):
    """Raised when a registered bot model cannot be loaded or used."""


@dataclass(frozen=True)
class ResolvedModel:
    name: str
    version: str
    uri: str
    run_id: str | None


def configure_mlflow(config_path: str = "config.yaml") -> str:
    settings = load_config(config_path)
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI") or settings.mlops.tracking_uri
    mlflow.set_tracking_uri(tracking_uri)
    return tracking_uri


def resolve_model(model_name: str, model_version: str | None = None, config_path: str = "config.yaml") -> ResolvedModel:
    configure_mlflow(config_path)
    client = MlflowClient()
    if model_version:
        version_info = client.get_model_version(model_name, str(model_version))
        return ResolvedModel(
            name=model_name,
            version=str(model_version),
            uri=f"models:/{model_name}/{model_version}",
            run_id=version_info.run_id,
        )

    versions = client.search_model_versions(f"name='{model_name}'")
    if not versions:
        raise ModelUnavailable(f"MLflow model not found in registry: {model_name}")

    latest = max(versions, key=lambda item: int(item.version))
    return ResolvedModel(
        name=model_name,
        version=str(latest.version),
        uri=f"models:/{model_name}/{latest.version}",
        run_id=latest.run_id,
    )


@lru_cache(maxsize=32)
def _load_feature_columns(run_id: str, config_path: str) -> tuple[str, ...] | None:
    """Colonnes attendues par le modele, dans l'ordre d'entrainement (artefact
    "feature_columns.json" logue par train_random_forest.py/train_xgboost.py dans le run
    MLflow associe). None si l'artefact n'existe pas -- cas des modeles plus anciens
    (ex. bot_rsi_reversal) qui transmettent les features telles quelles, sans filtrage.
    """
    configure_mlflow(config_path)
    try:
        path = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="feature_columns.json")
    except Exception:  # pragma: no cover - MLflow raises backend-specific "not found" exceptions
        return None
    with open(path, encoding="utf-8") as handle:
        return tuple(json.load(handle))


@lru_cache(maxsize=32)
def _load_sklearn_model(model_name: str, model_version: str, config_path: str) -> Any:
    configure_mlflow(config_path)
    uri = f"models:/{model_name}/{model_version}"
    try:
        return mlflow.sklearn.load_model(uri)
    except Exception as exc:  # pragma: no cover - MLflow raises backend-specific exceptions
        raise ModelUnavailable(f"Failed to load MLflow model {uri}: {exc}") from exc


def _class_labels(model: Any) -> list[str]:
    classes = getattr(model, "classes_", None)
    if classes is None and hasattr(model, "named_steps"):
        final_step = next(reversed(model.named_steps.values()))
        classes = getattr(final_step, "classes_", None)
    if classes is None:
        return []
    return [str(label).upper() for label in classes]


def list_trained_combos(config_path: str = "config.yaml") -> list[dict[str, str]]:
    """Couples (symbol, model_name) reellement entraines et disponibles dans le
    registre MLflow, parmi les modeles/paires actuellement configures cote app.

    Le nom d'enregistrement suit la convention "<model_name>_<symbol_lower>" (cf.
    models/src/training/train_random_forest.py et train_xgboost.py) : un modele entraine
    sous une ancienne configuration (paire ou modele retire depuis) est ignore ici,
    seuls les combos correspondant a l'etat actuel de utils/ (source unique de verite)
    sont retournes. C'est ce que BotMlClient.list_trained_combos() (backend/src/bots/
    ml_client.py) interroge pour savoir quels bots peuvent etre proposes/crees.
    """
    configure_mlflow(config_path)
    client = MlflowClient()
    registered_names = {model.name for model in client.search_registered_models()}

    combos = []
    for model_name in list_pair_qualified_models():
        for symbol in list_configured_symbols():
            registered_name = f"{model_name}_{symbol.lower()}"
            if registered_name in registered_names:
                combos.append({"symbol": symbol, "model_name": model_name, "registered_name": registered_name})
    return combos


def predict_registered_bot_model(
    *,
    model_name: str,
    features: dict[str, float],
    model_version: str | None = None,
    config_path: str = "config.yaml",
) -> dict[str, Any]:
    resolved = resolve_model(model_name, model_version, config_path)
    model = _load_sklearn_model(resolved.name, resolved.version, config_path)

    feature_columns = _load_feature_columns(resolved.run_id, config_path) if resolved.run_id else None
    if feature_columns is None:
        # Pas d'artefact feature_columns.json pour ce run (modeles plus anciens, ex.
        # bot_rsi_reversal) : le caller a deja transmis exactement les features attendues.
        frame = pd.DataFrame([features])
    else:
        missing = [column for column in feature_columns if column not in features]
        if missing:
            raise ModelUnavailable(f"Required features missing for {resolved.uri}: {', '.join(missing)}")
        frame = pd.DataFrame([{column: features[column] for column in feature_columns}])

    try:
        raw_signal = str(model.predict(frame)[0]).upper()
    except Exception as exc:
        raise ModelUnavailable(f"Failed to predict with MLflow model {resolved.uri}: {exc}") from exc
    if raw_signal not in {"BUY", "SELL", "HOLD"}:
        raise ModelUnavailable(f"MLflow model returned unsupported signal: {raw_signal}")

    probabilities: dict[str, float] = {}
    confidence = 1.0
    if hasattr(model, "predict_proba"):
        class_labels = _class_labels(model)
        proba = model.predict_proba(frame)[0]
        probabilities = {label: float(value) for label, value in zip(class_labels, proba, strict=False)}
        confidence = float(probabilities.get(raw_signal, max(probabilities.values()) if probabilities else 0.0))

    return {
        "model_source": "mlflow",
        "model_name": resolved.name,
        "model_version": resolved.version,
        "signal": raw_signal,
        "confidence": confidence,
        "probabilities": probabilities,
        "features": features,
        "generated_at": datetime.now(UTC).isoformat(),
    }
