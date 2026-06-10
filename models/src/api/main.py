"""FastAPI app for MVP signal serving."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from src.api.schemas import HealthResponse, ModelInfo, ModelsResponse, SignalResponse
from src.config.config_loader import load_config
from src.data.storage import read_dataset
from src.inference.signal import predict_random_forest_signal


app = FastAPI(title="CryptoBot Models Training API", version="0.1.0")


def get_settings():
    return load_config("config.yaml")


def registry_model_path(model_name: str) -> Path:
    settings = get_settings()
    return Path(settings.mlops.model_registry_path) / model_name / "best"


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    models = [name for name in ("random_forest", "lstm") if registry_model_path(name).exists()]
    return HealthResponse(status="ok" if models else "degraded", models_loaded=models)


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
