"""Tests unitaires pour la route POST /inference/predict-live."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from inference.router import router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _fake_service() -> MagicMock:
    """Un InferenceService factice : pas de vrai modèle chargé depuis MinIO."""
    svc = MagicMock()
    svc.feature_columns = ["rsi_14", "macd"]  # TODO: une liste courte suffit pour le test
    svc.model_name = "random_forest"
    svc.model_version = "minio"
    svc.predict.return_value = {
        "signal": "SELL",
        "signal_value": -1,
        "confidence": 0.72,
        "probabilities": {
            "0": 0.72,
            "1": 0.18,
            "2": 0.10
        },
        "latency_ms": 12.34,
    }
    return svc


def test_predict_live_returns_200_with_signal(client: TestClient) -> None:
    fake_df = pd.DataFrame([{"rsi_14": 55.0, "macd": 1.2}])  # une seule ligne suffit, iloc[-1] la prend

    with (
        patch("inference.router.build_live_feature_frame", return_value=fake_df),
        patch("inference.router.get_service", return_value=_fake_service()),
    ):
        response = client.post(
            "/inference/predict-live",
            json={"symbol": "BTCUSDT", "interval": "1h"},
        )

    assert response.status_code == 200
    data = response.json()

    assert "signal" in data
    assert "symbol" in data and data["symbol"] == "BTCUSDT"
