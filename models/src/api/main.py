"""FastAPI app for MVP signal serving."""

from __future__ import annotations

from pathlib import Path
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Query

from src.api.schemas import (
    BotModelPredictionRequest,
    BotModelPredictionResponse,
    HealthResponse,
    ModelInfo,
    ModelsResponse,
    SignalResponse,
)
from src.config.config_loader import load_config
from src.data.storage import read_dataset
from src.inference.mlflow_registry import ModelUnavailable, predict_registered_bot_model
from src.inference.signal import predict_random_forest_signal


app = FastAPI(title="CryptoBot Models Training API", version="0.1.0")


def get_settings():
    return load_config("config.yaml")


def registry_model_path(model_name: str) -> Path:
    settings = get_settings()
    return Path(settings.mlops.model_registry_path) / model_name / "best"


def default_features_path() -> Path:
    settings = get_settings()
    symbol = settings.data.symbols[0]
    interval = settings.data.primary_interval
    return Path(settings.data.paths.processed) / symbol.upper() / f"{interval}_features.{settings.data.formats.processed_primary}"


def latest_data_timestamp() -> tuple[str | None, int | None]:
    path = default_features_path()
    if not path.exists():
        return None, None
    features = read_dataset(path)
    if features.empty or "open_time" not in features.columns:
        return None, None
    timestamp = features.sort_values("open_time")["open_time"].iloc[-1]
    if not hasattr(timestamp, "isoformat"):
        return str(timestamp), None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC)
    freshness = int((datetime.now(UTC) - timestamp).total_seconds())
    return timestamp.isoformat(), freshness


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    models = [name for name in ("random_forest", "lstm") if registry_model_path(name).exists()]
    data_timestamp, freshness = latest_data_timestamp()
    has_inference_ready_model = "random_forest" in models
    status = "healthy" if has_inference_ready_model and data_timestamp is not None else "degraded"
    return HealthResponse(
        status=status,
        models_loaded=models,
        latest_data_timestamp=data_timestamp,
        data_freshness_seconds=freshness,
    )


@app.get("/models", response_model=ModelsResponse)
def models() -> ModelsResponse:
    items = []
    for name in ("random_forest", "lstm"):
        path = registry_model_path(name)
        items.append(ModelInfo(name=name, path=str(path), available=path.exists()))
    return ModelsResponse(models=items)


@app.get("/signals/latest", response_model=SignalResponse)
def latest_signal(
    symbol: str = Query(default="BTCUSDT"),
    interval: str = Query(default="1h"),
    model: str = Query(default="random_forest"),
) -> SignalResponse:
    settings = get_settings()
    if symbol.upper() not in settings.data.symbols:
        raise HTTPException(status_code=400, detail=f"Unsupported symbol: {symbol}")
    if interval not in settings.data.intervals:
        raise HTTPException(status_code=400, detail=f"Unsupported interval: {interval}")
    if model != "random_forest":
        raise HTTPException(status_code=404, detail=f"Model not available for MVP inference: {model}")

    artifact_path = registry_model_path(model)
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail=f"Model artifact not found: {artifact_path}")

    features_path = Path(settings.data.paths.processed) / symbol.upper() / f"{interval}_features.{settings.data.formats.processed_primary}"
    if not features_path.exists():
        raise HTTPException(status_code=503, detail=f"Processed dataset not found: {features_path}")

    features = read_dataset(features_path)
    prediction = predict_random_forest_signal(artifact_path, features, symbol=symbol, interval=interval)
    return SignalResponse(**prediction.to_dict())


@app.post("/bot-models/predict", response_model=BotModelPredictionResponse)
def predict_bot_model(payload: BotModelPredictionRequest) -> BotModelPredictionResponse:
    try:
        prediction = predict_registered_bot_model(
            model_name=payload.model_name,
            model_version=payload.model_version,
            features=payload.features,
        )
    except ModelUnavailable as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return BotModelPredictionResponse(**prediction)
