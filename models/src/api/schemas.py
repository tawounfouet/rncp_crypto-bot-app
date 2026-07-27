"""API response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str
    models_loaded: list[str]
    latest_data_timestamp: str | None = None
    data_freshness_seconds: int | None = None


class ModelInfo(BaseModel):
    name: str
    path: str
    available: bool


class ModelsResponse(BaseModel):
    models: list[ModelInfo]


class SignalResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    symbol: str
    interval: str
    model_name: str
    model_version: str
    signal: str
    signal_value: int
    confidence: float
    probabilities: dict[str, float]
    data_timestamp: str
    generated_at: str
    latency_ms: float
    warnings: list[str]


class BuildFeaturesRequest(BaseModel):
    symbols: list[str]
    interval: str
    config: str = "config.yaml"


class BuildFeaturesResult(BaseModel):
    symbol: str
    interval: str
    rows: int


class BuildFeaturesResponse(BaseModel):
    results: list[BuildFeaturesResult]


class TrainRandomForestRequest(BaseModel):
    dataset: str
    config: str = "config.yaml"


class TrainRandomForestResponse(BaseModel):
    artifact_dir: str
