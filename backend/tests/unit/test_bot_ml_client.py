"""Tests unitaires pour bots/ml_client.py::BotMlClient.list_trained_combos()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests
from bots.ml_client import BotMlClient, BotModelUnavailable


def test_list_trained_combos_returns_combos_from_ml_api():
    fake_combos = [
        {"symbol": "BTCUSDC", "model_name": "random_forest", "registered_name": "random_forest_btcusdc"},
        {"symbol": "ETHUSDC", "model_name": "xgboost", "registered_name": "xgboost_ethusdc"},
    ]
    fake_response = MagicMock()
    fake_response.json.return_value = {"combos": fake_combos}
    fake_response.raise_for_status.return_value = None

    with patch("bots.ml_client.requests.get", return_value=fake_response) as mock_get:
        combos = BotMlClient(base_url="http://ml-api-test:8010").list_trained_combos()

    assert combos == fake_combos
    mock_get.assert_called_once_with("http://ml-api-test:8010/bot-models/trained-combos", timeout=10.0)


def test_list_trained_combos_raises_when_ml_api_unreachable():
    with patch("bots.ml_client.requests.get", side_effect=requests.ConnectionError("refused")):
        with pytest.raises(BotModelUnavailable, match="ML API unavailable"):
            BotMlClient().list_trained_combos()


def test_list_trained_combos_raises_on_malformed_response():
    fake_response = MagicMock()
    fake_response.json.return_value = {"unexpected": "shape"}
    fake_response.raise_for_status.return_value = None

    with patch("bots.ml_client.requests.get", return_value=fake_response):
        with pytest.raises(BotModelUnavailable, match="invalid trained-combos response"):
            BotMlClient().list_trained_combos()
