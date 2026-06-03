from __future__ import annotations

from schemas.bot import BotConfigUpdate
from services.bot_config_service import BotConfigService


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


def test_bot_config_save_increments_version(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = BotConfigService(store)
    previous = store.bot_configs["bot_btc_scalp"].version
    ok, _, config = service.save(
        "bot_btc_scalp",
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
    assert config.version == previous + 1
