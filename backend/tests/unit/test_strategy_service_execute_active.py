"""Tests unitaires pour StrategyService.execute_strategy.execute_active."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from auth.models import User
from strategy.models import Strategy, StrategyDeployment, StrategyState
from strategy.service import StrategyService


def _make_user(session) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=f"{uuid.uuid4()}@test.dev",
        username=f"user_{uuid.uuid4().hex[:8]}",
        hashed_password="fake",  # noqa: S106
    )
    session.add(user)
    session.flush()
    return user

def _make_ml_deployment(session, user: User) -> StrategyDeployment:
    strategy = Strategy(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name="Bot test RF",
        strategy_type="ml_random_forest",
        parameters={},
    )
    session.add(strategy)
    session.flush()

    deployment = StrategyDeployment(
        id=str(uuid.uuid4()),
        strategy_id=strategy.id,
        user_id=user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe="1h",
        amount=100,
        status="active",
        start_time=datetime.now(UTC),
    )
    session.add(deployment)
    session.flush()
    return deployment


def _make_state(session, deployment: StrategyDeployment, position="NEUTRAL", last_signal_time=None) -> StrategyState:
    state = StrategyState(
        id=str(uuid.uuid4()),
        deployment_id=deployment.id,
        user_id=deployment.user_id,
        position=position,
        last_signal_time=last_signal_time
    )
    session.add(state)
    session.flush()
    return state

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
async def test_execute_active_deployments_activ_cooldown(patch_db_session) -> None:
    user = _make_user(patch_db_session)
    deployment = _make_ml_deployment(patch_db_session, user)
    state = _make_state(patch_db_session, deployment, "NEUTRAL", datetime.now(UTC))

    service = StrategyService(market_data_service=MagicMock())
    with patch.object(service, "execute_strategy"):
        response = await service.execute_active_deployments()

        service.execute_strategy.assert_not_called()
        assert response[0]["action"] == "skipped_cooldown"


@pytest.mark.asyncio
async def test_execute_active_deployments_position_opened(patch_db_session) -> None:
    user = _make_user(patch_db_session)
    deployment = _make_ml_deployment(patch_db_session, user)
    state = _make_state(patch_db_session, deployment, "LONG")

    service = StrategyService(market_data_service=MagicMock())
    with patch.object(service, "execute_strategy"):
        response = await service.execute_active_deployments()

        service.execute_strategy.assert_not_called()
        assert response[0]["action"] == "skipped_open_position"


@pytest.mark.asyncio
async def test_execute_active_deployments_signal_hold(patch_db_session, mock_trading_service) -> None:
    user = _make_user(patch_db_session)
    _make_ml_deployment(patch_db_session, user)

    service = StrategyService(market_data_service=MagicMock())
    with patch.object(service, "execute_strategy") as mock_execute_strategy:
        mock_execute_strategy.return_value = {"latest_signal": 0, "signal_info": {}}
        response = await service.execute_active_deployments()

        mock_trading_service.create_order.assert_not_called()

        assert response[0]["action"] == "hold"


@pytest.mark.asyncio
async def test_execute_active_deployments_signal_buy_sell(patch_db_session, mock_trading_service) -> None:
    user = _make_user(patch_db_session)
    deployment = _make_ml_deployment(patch_db_session, user)

    service = StrategyService(market_data_service=MagicMock())
    with patch.object(service, "execute_strategy") as mock_execute_strategy:
        mock_execute_strategy.return_value = {"latest_signal": 1, "signal_info": {"price": 50000}}
        response = await service.execute_active_deployments()

        mock_trading_service.create_order.assert_called_once()
        called_user_id, order_data = mock_trading_service.create_order.call_args.args
        assert called_user_id == user.id
        assert order_data.quantity == deployment.amount / Decimal("50000")

        assert response[0]["action"] == "order_submitted"
