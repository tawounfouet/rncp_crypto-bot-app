"""Tests unitaires pour StrategyService (execute_strategy + execute_active_deployments)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
import requests
from strategy.service import StrategyService


class _FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200) -> None:
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self) -> dict:
        return self._json


@pytest.fixture
def mock_from_user_settings():
    with patch("market.clients.factory.from_user_settings") as mock:
        yield mock


@pytest.fixture
def mock_trading_service():
    with patch("strategy.service.TradingService") as mock_cls:
        # create_order est une coroutine sur le vrai TradingService : sans ca,
        # `await trading_service.create_order(...)` plante sur un MagicMock non-awaitable.
        mock_cls.return_value.create_order = AsyncMock()
        yield mock_cls.return_value


@pytest.mark.asyncio
async def test_execute_strategy_ml_random_forest_calls_inference(
        patch_db_session,
        make_user,
        make_deployment,
        make_state
    ) -> None:
    user = make_user(patch_db_session)
    deployment = make_deployment(patch_db_session, user)
    state = make_state(patch_db_session, deployment)

    fake_features_df = pd.DataFrame([{"ema_12": 55.0, "macd_signal": 1.2}])

    fake_predict_result = {
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

    service = StrategyService(market_data_service=MagicMock())

    with (
        patch("strategy.service.build_live_feature_frame", return_value=fake_features_df),
        patch("strategy.service.InferenceService") as mock_inference_cls,
    ):
        mock_inference_cls.return_value.feature_columns = list(fake_features_df.columns)
        mock_inference_cls.return_value.predict.return_value = fake_predict_result

        result = await service.execute_strategy(deployment.id)

        patch_db_session.refresh(state)


    assert result["latest_signal"] == fake_predict_result["signal_value"]
    assert result["signal_info"]["confidence"] == fake_predict_result["confidence"]
    assert result["signal_info"]["probabilities"] == fake_predict_result["probabilities"]
    assert result["data_points"] == len(fake_features_df)

    assert state.last_signal_time is not None
    assert state.last_signal == "SELL"


@pytest.mark.asyncio
async def test_execute_active_deployments_activ_cooldown(
        patch_db_session,
        make_user,
        make_deployment,
        make_state
    ) -> None:
    user = make_user(patch_db_session)
    deployment = make_deployment(patch_db_session, user)
    make_state(patch_db_session, deployment, "NEUTRAL", datetime.now(UTC))

    service = StrategyService(market_data_service=MagicMock())
    with patch.object(service, "execute_strategy"):
        response = await service.execute_active_deployments()

        service.execute_strategy.assert_not_called()
        assert response[0]["action"] == "skipped_cooldown"


@pytest.mark.asyncio
async def test_execute_active_deployments_position_opened(
        patch_db_session,
        make_user,
        make_deployment,
        make_state
    ) -> None:
    user = make_user(patch_db_session)
    deployment = make_deployment(patch_db_session, user)
    make_state(patch_db_session, deployment, "LONG")

    service = StrategyService(market_data_service=MagicMock())
    with patch.object(service, "execute_strategy"):
        response = await service.execute_active_deployments()

        service.execute_strategy.assert_not_called()
        assert response[0]["action"] == "skipped_open_position"


@pytest.mark.asyncio
async def test_execute_active_deployments_signal_hold(
        patch_db_session,
        make_user,
        make_deployment,
        make_state,
        mock_trading_service
    ) -> None:
    user = make_user(patch_db_session)
    make_deployment(patch_db_session, user)

    service = StrategyService(market_data_service=MagicMock())
    with patch.object(service, "execute_strategy") as mock_execute_strategy:
        mock_execute_strategy.return_value = {"latest_signal": 0, "signal_info": {}}
        response = await service.execute_active_deployments()

        mock_trading_service.create_order.assert_not_called()

        assert response[0]["action"] == "hold"


@pytest.mark.asyncio
async def test_execute_active_deployments_signal_buy_sell(
        patch_db_session,
        make_user,
        make_deployment,
        mock_trading_service
    ) -> None:
    user = make_user(patch_db_session)
    deployment = make_deployment(patch_db_session, user)

    service = StrategyService(market_data_service=MagicMock())
    with patch.object(service, "execute_strategy") as mock_execute_strategy:
        mock_execute_strategy.return_value = {"latest_signal": 1, "signal_info": {"price": 50000}}
        response = await service.execute_active_deployments()

        mock_trading_service.create_order.assert_called_once()
        called_user_id, order_data = mock_trading_service.create_order.call_args.args
        assert called_user_id == user.id
        assert order_data.quantity == deployment.amount / Decimal("50000")

        assert response[0]["action"] == "order_submitted"


def test_get_available_models_returns_models_list() -> None:
    fake_models = {
        "models": [
            {"name": "random_forest", "path": "/registry/rf/best", "available": True},
            {"name": "lstm", "path": "/registry/lstm/best", "available": False},
        ]
    }
    service = StrategyService(market_data_service=MagicMock())

    with patch("strategy.service.requests.get", return_value=_FakeResponse(fake_models)) as mock_get:
        result = service.get_available_models()

    assert result == fake_models["models"]
    mock_get.assert_called_once()
    called_url = mock_get.call_args.args[0]
    assert called_url.endswith("/models")


def test_get_available_models_raises_on_ml_api_error() -> None:
    service = StrategyService(market_data_service=MagicMock())

    with patch("strategy.service.requests.get", return_value=_FakeResponse({}, status_code=502)):
        with pytest.raises(requests.HTTPError):
            service.get_available_models()
