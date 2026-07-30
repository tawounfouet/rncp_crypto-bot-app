"""Tests unitaires des endpoints marché publics (pas d'authentification)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from market.router import router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_list_public_exchanges_returns_configured_exchanges(client: TestClient) -> None:
    response = client.get("/market/exchanges")

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["data"]}
    assert {"binance", "kraken"}.issubset(ids)


def test_list_public_exchanges_reports_sandbox_support_per_exchange(client: TestClient) -> None:
    response = client.get("/market/exchanges")

    by_id = {item["id"]: item["supports_sandbox"] for item in response.json()["data"]}
    assert by_id["binance"] is True
    assert by_id["kraken"] is False  # pas de testnet Spot self-service


def test_list_public_exchanges_requires_no_authentication(client: TestClient) -> None:
    response = client.get("/market/exchanges")  # aucun header Authorization envoyé

    assert response.status_code == 200


def test_get_public_prices_uses_market_data_driver(client: TestClient) -> None:
    fake_driver = MagicMock()
    fake_driver.fetch_klines.return_value = [{"close": 65000.0, "close_time": datetime.now(UTC)}]

    with patch("market.router.get_market_data_driver", return_value=fake_driver) as get_driver:
        response = client.get("/market/public/prices", params={"exchange": "binance", "symbols": "BTCUSDT"})

    get_driver.assert_called_once_with("binance")
    fake_driver.fetch_klines.assert_called_once_with("BTCUSDT", "1m", limit=1)
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    entry = body["data"][0]
    assert entry["symbol"] == "BTCUSDT"
    assert entry["exchange"] == "binance"
    assert float(entry["price"]) == 65000.0
    assert body["warnings"] == []


def test_get_public_prices_collects_warning_on_driver_failure(client: TestClient) -> None:
    fake_driver = MagicMock()
    fake_driver.fetch_klines.side_effect = RuntimeError("boom")

    with patch("market.router.get_market_data_driver", return_value=fake_driver):
        response = client.get("/market/public/prices", params={"exchange": "kraken", "symbols": "BTCUSDT"})

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert len(body["warnings"]) == 1


def test_get_public_prices_defaults_to_binance_and_default_symbols(client: TestClient) -> None:
    fake_driver = MagicMock()
    fake_driver.fetch_klines.return_value = [{"close": 1.0, "close_time": datetime.now(UTC)}]

    with patch("market.router.get_market_data_driver", return_value=fake_driver) as get_driver:
        response = client.get("/market/public/prices")

    get_driver.assert_called_once_with("binance")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2  # DEFAULT_PUBLIC_SYMBOLS = BTCUSDT, ETHUSDT


def test_get_public_klines_uses_market_data_driver(client: TestClient) -> None:
    fake_driver = MagicMock()
    fake_driver.fetch_klines.return_value = [
        {
            "open_time": datetime.now(UTC),
            "open": 64900.0,
            "high": 65100.0,
            "low": 64800.0,
            "close": 65000.0,
            "volume": 12.5,
        }
    ]

    with patch("market.router.get_market_data_driver", return_value=fake_driver) as get_driver:
        response = client.get("/market/public/klines", params={"exchange": "binance", "symbols": "BTCUSDT"})

    get_driver.assert_called_once_with("binance")
    fake_driver.fetch_klines.assert_called_once_with("BTCUSDT", "1h", limit=24)  # defauts de l'endpoint
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    entry = body["data"][0]
    assert entry["symbol"] == "BTCUSDT"
    assert entry["exchange"] == "binance"
    assert entry["interval"] == "1h"
    assert float(entry["open"]) == 64900.0
    assert float(entry["high"]) == 65100.0
    assert float(entry["low"]) == 64800.0
    assert float(entry["close"]) == 65000.0
    assert float(entry["volume"]) == 12.5
    assert body["warnings"] == []


def test_get_public_klines_returns_full_series_not_just_latest(client: TestClient) -> None:
    """Regression : /public/klines doit renvoyer toute la serie, pas juste la derniere bougie."""
    fake_driver = MagicMock()
    fake_driver.fetch_klines.return_value = [
        {"open_time": datetime.now(UTC), "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
        {"open_time": datetime.now(UTC), "open": 2.0, "high": 2.0, "low": 2.0, "close": 2.0, "volume": 2.0},
        {"open_time": datetime.now(UTC), "open": 3.0, "high": 3.0, "low": 3.0, "close": 3.0, "volume": 3.0},
    ]

    with patch("market.router.get_market_data_driver", return_value=fake_driver):
        response = client.get(
            "/market/public/klines", params={"exchange": "binance", "symbols": "BTCUSDT", "limit": 3}
        )

    assert response.status_code == 200
    assert len(response.json()["data"]) == 3


def test_get_public_klines_collects_warning_on_driver_failure(client: TestClient) -> None:
    fake_driver = MagicMock()
    fake_driver.fetch_klines.side_effect = RuntimeError("boom")

    with patch("market.router.get_market_data_driver", return_value=fake_driver):
        response = client.get("/market/public/klines", params={"exchange": "kraken", "symbols": "BTCUSDT"})

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert len(body["warnings"]) == 1
