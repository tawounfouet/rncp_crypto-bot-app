from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schemas.bot import BotConfigUpdate
from services.api_client import BackendApiClient
from services.auth_api_client import ApiResponse
from services.base import ServiceError
from services.bot_config_service import BotConfigService

MOCK_STRATEGY = {
    "id": "strat_btc",
    "name": "BTC Scalp",
    "strategy_type": "scalping",
    "is_active": True,
    "updated_at": "2024-01-01T00:00:00Z",
    "parameters": {
        "budget_usdt": 5000.0,
        "max_open_positions": 3,
        "risk_per_trade_pct": 1.0,
        "take_profit_pct": 3.0,
        "stop_loss_pct": 2.0,
        "cooldown_seconds": 300,
        "version": 1,
    },
}


def _ok(data: object) -> ApiResponse:
    return ApiResponse(status_code=200, data=data)


@pytest.fixture(autouse=True)
def _mock_token():
    with patch("services.bot_config_service.get_access_token", return_value="fake-token"):
        yield


def test_bot_config_validate_errors(store) -> None:
    service = BotConfigService(store)
    errors = service.validate(
        BotConfigUpdate(
            strategy="Breakout",
            budget_usdt=-1.0,
            max_open_positions=0,
            risk_per_trade_pct=99.0,
            take_profit_pct=0.0,
            stop_loss_pct=0.0,
            cooldown_seconds=-3,
        )
    )
    assert len(errors) >= 3


def test_bot_config_validate_clean(store) -> None:
    service = BotConfigService(store)
    errors = service.validate(
        BotConfigUpdate(
            strategy="Scalping",
            budget_usdt=1000.0,
            max_open_positions=3,
            risk_per_trade_pct=1.0,
            take_profit_pct=3.0,
            stop_loss_pct=2.0,
            cooldown_seconds=300,
        )
    )
    assert errors == []


def test_bot_config_save_increments_version(store) -> None:
    updated_strategy = {
        **MOCK_STRATEGY,
        "parameters": {
            **MOCK_STRATEGY["parameters"],
            "budget_usdt": 8000.0,
            "max_open_positions": 4,
            "version": 2,
        },
    }
    client = MagicMock(spec=BackendApiClient)
    client.get_strategy.return_value = _ok(MOCK_STRATEGY)
    client.update_strategy.return_value = _ok(updated_strategy)
    service = BotConfigService(store, client=client)
    ok, _, config = service.save(
        "strat_btc",
        BotConfigUpdate(
            strategy="Mean Reversion",
            budget_usdt=8000.0,
            max_open_positions=4,
            risk_per_trade_pct=1.5,
            take_profit_pct=3.0,
            stop_loss_pct=1.8,
            cooldown_seconds=90,
        ),
    )
    assert ok is True
    assert config is not None
    assert config.version == 2
    client.update_strategy.assert_called_once()


def test_bot_config_save_validation_failure_skips_backend(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    service = BotConfigService(store, client=client)
    ok, message, config = service.save(
        "strat_btc",
        BotConfigUpdate(
            strategy="Bad",
            budget_usdt=-1.0,
            max_open_positions=0,
            risk_per_trade_pct=1.0,
            take_profit_pct=1.0,
            stop_loss_pct=1.0,
            cooldown_seconds=0,
        ),
    )
    assert ok is False
    assert config is None
    client.update_strategy.assert_not_called()


def test_bot_config_save_sends_strategy_type(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_strategy.return_value = _ok(MOCK_STRATEGY)
    client.update_strategy.return_value = _ok(MOCK_STRATEGY)
    service = BotConfigService(store, client=client)
    service.save(
        "strat_btc",
        BotConfigUpdate(
            strategy="ml_random_forest",
            budget_usdt=8000.0,
            max_open_positions=4,
            risk_per_trade_pct=1.5,
            take_profit_pct=3.0,
            stop_loss_pct=1.8,
            cooldown_seconds=90,
        ),
    )
    _, _, payload = client.update_strategy.call_args.args
    assert payload["strategy_type"] == "ml_random_forest"


def test_get_available_models_returns_data_list(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    fake_models = [
        {"name": "random_forest", "path": "/registry/rf/best", "available": True},
        {"name": "lstm", "path": "/registry/lstm/best", "available": False},
    ]
    client.get_available_models.return_value = _ok({"success": True, "data": fake_models})
    service = BotConfigService(store, client=client)

    result = service.get_available_models()

    assert result == fake_models


def test_get_available_models_raises_on_backend_error(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.get_available_models.return_value = ApiResponse(status_code=502, error="ml-api down")
    service = BotConfigService(store, client=client)

    with pytest.raises(ServiceError):
        service.get_available_models()


def test_create_bot_calls_client_with_prefixed_strategy_type(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.create_strategy.return_value = _ok(MOCK_STRATEGY)
    service = BotConfigService(store, client=client)

    service.create_bot(name="Mon bot RF", strategy_type="ml_random_forest")

    client.create_strategy.assert_called_once_with(
        "fake-token", name="Mon bot RF", strategy_type="ml_random_forest"
    )


def test_create_bot_raises_on_backend_error(store) -> None:
    client = MagicMock(spec=BackendApiClient)
    client.create_strategy.return_value = ApiResponse(status_code=400, error="Unknown strategy type")
    service = BotConfigService(store, client=client)

    with pytest.raises(ServiceError):
        service.create_bot(name="Mon bot RF", strategy_type="ml_random_forest")
