from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """Request payload for model inference.

    Accepts pre-computed feature values matching the model's ``feature_columns.json``.
    """

    symbol: str = Field(..., description="Trading pair (e.g. BTCUSDC)")
    interval: str = Field("1h", description="Kline interval")
    features: dict[str, float] = Field(
        ...,
        description="Feature name → value mapping. Must include all columns from feature_columns.json",
    )


class PredictLiveRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair (e.g. BTCUSDC)")
    interval: str = Field("1h", description="Kline interval")


class PredictResponse(BaseModel):
    """Inference result."""

    success: bool = True
    symbol: str
    interval: str
    model_name: str
    model_version: str
    signal: str
    signal_value: int
    confidence: float
    probabilities: dict[str, float]
    latency_ms: float
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    warnings: list[str] = Field(default_factory=list)


class ModelInfoResponse(BaseModel):
    """Information about the deployed model."""

    success: bool = True
    model_name: str
    model_version: str
    feature_columns: list[str]
    artifact_path: str
    loaded: bool
