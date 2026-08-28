from __future__ import annotations

import importlib.util
import sys

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11)
    or importlib.util.find_spec("fastapi") is None
    or importlib.util.find_spec("mlflow") is None,
    reason="Python 3.11+, fastapi and mlflow are required for ML API tests",
)


def test_bot_model_prediction_endpoint_returns_mlflow_signal(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api import main as api_main

    def fake_predict_registered_bot_model(**kwargs):
        return {
            "model_source": "mlflow",
            "model_name": kwargs["model_name"],
            "model_version": "3",
            "signal": "BUY",
            "confidence": 0.82,
            "probabilities": {"BUY": 0.82, "SELL": 0.08, "HOLD": 0.10},
            "features": kwargs["features"],
            "generated_at": "2026-06-27T00:00:00+00:00",
        }

    monkeypatch.setattr(api_main, "predict_registered_bot_model", fake_predict_registered_bot_model)
    response = TestClient(api_main.app).post(
        "/bot-models/predict",
        json={
            "model_name": "bot_rsi_reversal_btcusdt_1h",
            "features": {
                "rsi": 42,
                "price_change": 0.001,
                "volume": 120,
                "sma_short": 65000,
                "sma_long": 64800,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_source"] == "mlflow"
    assert payload["signal"] == "BUY"
    assert payload["model_version"] == "3"


def test_trained_combos_endpoint_returns_registry_combos(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api import main as api_main

    fake_combos = [
        {"symbol": "BTCUSDC", "model_name": "random_forest", "registered_name": "random_forest_btcusdc"},
    ]
    monkeypatch.setattr(api_main, "list_trained_combos", lambda: fake_combos)
    response = TestClient(api_main.app).get("/bot-models/trained-combos")

    assert response.status_code == 200
    assert response.json() == {"combos": fake_combos}


def test_bot_model_prediction_endpoint_reports_missing_model(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api import main as api_main
    from src.inference.mlflow_registry import ModelUnavailable

    def fake_predict_registered_bot_model(**kwargs):
        raise ModelUnavailable("MLflow model not found in registry")

    monkeypatch.setattr(api_main, "predict_registered_bot_model", fake_predict_registered_bot_model)
    response = TestClient(api_main.app).post(
        "/bot-models/predict",
        json={
            "model_name": "bot_rsi_reversal_btcusdt_1h",
            "features": {
                "rsi": 42,
                "price_change": 0.001,
                "volume": 120,
                "sma_short": 65000,
                "sma_long": 64800,
            },
        },
    )

    assert response.status_code == 404
    assert "MLflow model not found" in response.json()["detail"]
