from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schemas.common import BotRuntimeStatus
from services.api_client import BackendApiClient
from services.auth_api_client import ApiResponse
from services.bot_control_service import BotControlService
from utils.constants import ACTION_PAUSE, ACTION_START, ACTION_STOP

MOCK_STRATEGIES = [
    {
        "id": "strat_btc",
        "name": "BTC Scalp",
        "strategy_type": "scalping",
        "is_active": True,
        "updated_at": "2024-01-01T00:00:00Z",
    },
    {
        "id": "strat_sol",
        "name": "SOL Trend",
        "strategy_type": "trend",
        "is_active": True,
        "updated_at": "2024-01-01T00:00:00Z",
    },
]

MOCK_DEPLOYMENTS = [
    {
        "id": "deploy_1",
        "strategy_id": "strat_sol",
        "status": "active",
        "updated_at": "2024-01-01T00:00:00Z",
    },
]


def _ok(data: object) -> ApiResponse:
    return ApiResponse(status_code=200, data=data)


@pytest.fixture(autouse=True)
def _mock_token():
    with patch("services.bot_control_service.get_access_token", return_value="fake-token"):
        yield


def test_list_bots(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.list_strategies.return_value = _ok(MOCK_STRATEGIES)
    client.list_deployments.return_value = _ok(MOCK_DEPLOYMENTS)
    service = BotControlService(store, client=client)
    bots = service.list_bots()
    assert len(bots) == 2
    sol_bot = next(b for b in bots if b.id == "strat_sol")
    assert sol_bot.status == BotRuntimeStatus.RUNNING
    btc_bot = next(b for b in bots if b.id == "strat_btc")
    assert btc_bot.status == BotRuntimeStatus.STOPPED


def test_bot_stop_with_active_deployment(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.list_strategies.return_value = _ok(MOCK_STRATEGIES)
    client.list_deployments.return_value = _ok(MOCK_DEPLOYMENTS)
    client.stop_deployment.return_value = _ok({"message": "stopped"})
    service = BotControlService(store, client=client)
    service.list_bots()  # populate _active_deployments
    result = service.apply_action("strat_sol", ACTION_STOP)
    assert result.success is True
    client.stop_deployment.assert_called_once_with("fake-token", "deploy_1")


def test_bot_stop_no_active_deployment(store) -> None:
    service = BotControlService(store, client=MagicMock())
    result = service.apply_action("strat_btc", ACTION_STOP)
    assert result.success is False


def test_bot_start_returns_informative_failure(store) -> None:
    service = BotControlService(store, client=MagicMock())
    result = service.apply_action("strat_btc", ACTION_START)
    assert result.success is False
    assert len(result.message) > 0


def test_bot_pause_not_supported(store) -> None:
    service = BotControlService(store, client=MagicMock())
    result = service.apply_action("strat_btc", ACTION_PAUSE)
    assert result.success is False


def test_start_bot_success(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.deploy_strategy.return_value = _ok({"id": "deploy_2", "status": "active"})
    service = BotControlService(store, client=client)

    result = service.start_bot(
        "strat_btc",
        exchange="binance",
        symbol="BTCUSDC",
        timeframe="1h",
        amount=100.0,
        is_paper=True,
    )

    assert result.success is True
    client.deploy_strategy.assert_called_once_with(
        "fake-token",
        "strat_btc",
        exchange="binance",
        symbol="BTCUSDC",
        timeframe="1h",
        amount=100.0,
        is_paper=True,
    )


def test_start_bot_failure_returns_backend_message(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.deploy_strategy.return_value = ApiResponse(status_code=400, error="Strategie invalide")
    service = BotControlService(store, client=client)

    result = service.start_bot(
        "strat_btc",
        exchange="binance",
        symbol="BTCUSDC",
        timeframe="1h",
        amount=100.0,
        is_paper=True,
    )

    assert result.success is False
    assert result.message == "Strategie invalide"
