"""FastAPI app for MVP signal serving."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from src.api.schemas import (
    BuildFeaturesRequest,
    BuildFeaturesResponse,
    BuildFeaturesResult,
    HealthResponse,
    ModelInfo,
    ModelsResponse,
    SignalResponse,
    TrainMLPRequest,
    TrainMLPResponse,
    TrainRandomForestRequest,
    TrainRandomForestResponse,
    TrainXGBoostRequest,
    TrainXGBoostResponse,
)
from src.config.config_loader import load_config
from src.data.storage import read_dataset
from src.features.build import build_symbol_features
from src.inference.signal import INFERENCE_MODELS, predict_model_signal
from src.training.train_mlp import train_from_processed_dataset as train_mlp_from_processed_dataset
from src.training.train_random_forest import train_from_processed_dataset
from src.training.train_xgboost import train_from_processed_dataset as train_xgboost_from_processed_dataset


app = FastAPI(title="CryptoBot Models Training API", version="0.1.0")


def get_settings():
    return load_config("config.yaml")


def registry_model_path(model_name: str) -> Path:
    settings = get_settings()
    return Path(settings.mlops.model_registry_path) / model_name / "best"


# Modeles exposes par /models (entraines via config.yaml) — l'inférence
# n'est servie que pour INFERENCE_MODELS (layout joblib partage).
AVAILABLE_MODELS = ("random_forest", "mlp", "xgboost", "lstm")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    models = [name for name in AVAILABLE_MODELS if registry_model_path(name).exists()]
    return HealthResponse(status="ok" if models else "degraded", models_loaded=models)


@app.get("/models", response_model=ModelsResponse)
def models() -> ModelsResponse:
    items = []
    for name in AVAILABLE_MODELS:
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
    if model not in INFERENCE_MODELS:
        raise HTTPException(status_code=404, detail=f"Model not available for MVP inference: {model}")

    artifact_path = registry_model_path(model)
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail=f"Model artifact not found: {artifact_path}")

    features_path = (
        Path(settings.data.paths.processed)
        / symbol.upper()
        / f"{interval}_features.{settings.data.formats.processed_primary}"
    )
    if not features_path.exists():
        raise HTTPException(status_code=503, detail=f"Processed dataset not found: {features_path}")

    features = read_dataset(features_path)
    prediction = predict_model_signal(model, artifact_path, features, symbol=symbol, interval=interval)
    return SignalResponse(**prediction.to_dict())


# ---------------------------------------------------------------------------
# Pipeline interne (declenche par le DAG Airflow cryptobot_ml_pipeline).
#
# Ces routes existent pour que l'orchestrateur (Airflow) n'ait jamais besoin
# d'installer torch/mlflow/scikit-learn dans son propre environnement Python :
# ce conteneur (crypto-bot-ml-api) a deja ces dependances qui fonctionnent,
# le DAG se contente d'un appel HTTP. Pas d'authentification car ces routes ne
# sont joignables que depuis le reseau Docker interne (pas de port expose pour
# elles specifiquement, /app/... est deja publie mais reserve a un usage
# orchestrateur -> reseau interne dans ce projet).
# ---------------------------------------------------------------------------


@app.post("/internal/pipeline/features", response_model=BuildFeaturesResponse)
def build_features(request: BuildFeaturesRequest) -> BuildFeaturesResponse:
    results = []
    for symbol in request.symbols:
        try:
            frame = build_symbol_features(symbol, request.interval, request.config)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"build_symbol_features failed for {symbol}: {exc}") from exc
        results.append(BuildFeaturesResult(symbol=symbol.upper(), interval=request.interval, rows=len(frame)))
    return BuildFeaturesResponse(results=results)


@app.post("/internal/pipeline/train-rf", response_model=TrainRandomForestResponse)
def train_random_forest_endpoint(request: TrainRandomForestRequest) -> TrainRandomForestResponse:
    try:
        artifact_dir = train_from_processed_dataset(request.dataset, request.config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"train_random_forest failed: {exc}") from exc
    return TrainRandomForestResponse(artifact_dir=str(artifact_dir))


@app.post("/internal/pipeline/train-mlp", response_model=TrainMLPResponse)
def train_mlp_endpoint(request: TrainMLPRequest) -> TrainMLPResponse:
    try:
        artifact_dir = train_mlp_from_processed_dataset(request.dataset, request.config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"train_mlp failed: {exc}") from exc
    return TrainMLPResponse(artifact_dir=str(artifact_dir))


@app.post("/internal/pipeline/train-xgboost", response_model=TrainXGBoostResponse)
def train_xgboost_endpoint(request: TrainXGBoostRequest) -> TrainXGBoostResponse:
    try:
        artifact_dir = train_xgboost_from_processed_dataset(request.dataset, request.config)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"train_xgboost failed: {exc}") from exc
    return TrainXGBoostResponse(artifact_dir=str(artifact_dir))
