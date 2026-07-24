"""Signal prediction contracts and helpers."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from src.config.dependencies import require_dependency


@dataclass(frozen=True)
class SignalPrediction:
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

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "signal": self.signal,
            "signal_value": self.signal_value,
            "confidence": self.confidence,
            "probabilities": self.probabilities,
            "data_timestamp": self.data_timestamp,
            "generated_at": self.generated_at,
            "latency_ms": self.latency_ms,
            "warnings": self.warnings,
        }


SIGNAL_VALUES = {"SELL": -1, "HOLD": 0, "BUY": 1}


def predict_random_forest_signal(
    artifact_dir: str | Path,
    features: pd.DataFrame,
    symbol: str,
    interval: str,
) -> SignalPrediction:
    """Predict latest signal from a Random Forest artifact directory."""
    require_dependency("joblib", "Run `pip install -r requirements.txt` before Random Forest inference.")
    import joblib

    start = time.perf_counter()
    artifact_path = Path(artifact_dir)
    model = joblib.load(artifact_path / "model.joblib")
    scaler = joblib.load(artifact_path / "scaler.joblib")
    feature_columns = json.loads((artifact_path / "feature_columns.json").read_text(encoding="utf-8"))

    latest = features.sort_values("open_time").iloc[-1:]
    x_latest = scaler.transform(latest[feature_columns])
    probabilities_array = model.predict_proba(x_latest)[0]
    classes = list(model.classes_)
    probabilities = {str(label): float(prob) for label, prob in zip(classes, probabilities_array, strict=True)}
    signal = max(probabilities, key=probabilities.get)
    latency_ms = (time.perf_counter() - start) * 1000
    timestamp = latest["open_time"].iloc[0]
    if hasattr(timestamp, "isoformat"):
        data_timestamp = timestamp.isoformat()
    else:
        data_timestamp = str(timestamp)
    return SignalPrediction(
        symbol=symbol.upper(),
        interval=interval,
        model_name="random_forest",
        model_version=artifact_path.parent.name if artifact_path.name == "best" else artifact_path.name,
        signal=signal,
        signal_value=SIGNAL_VALUES.get(signal, 0),
        confidence=probabilities[signal],
        probabilities=probabilities,
        data_timestamp=data_timestamp,
        generated_at=datetime.now(tz=UTC).isoformat(),
        latency_ms=latency_ms,
        warnings=[],
    )
