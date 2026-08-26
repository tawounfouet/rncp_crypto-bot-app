"""Base de donnees mockee en memoire."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from mocks.scenarios import MockScenario
from schemas.auth import MockUser
from schemas.bot import BotInfo, BotTemplate, UserBotSelection
from schemas.common import BotRuntimeStatus, UserRole, UserStatus

SEED = 42


@dataclass
class MockStore:
    users: dict[str, MockUser]
    bots: dict[str, BotInfo]
    bot_templates: dict[str, BotTemplate]
    user_bot_selections: dict[str, list[UserBotSelection]]
    binance_credentials: dict[str, tuple[str, str]]
    credential_updated_at: dict[str, datetime]
    current_user_email: str | None = None
    scenario: MockScenario = MockScenario.USER_NORMAL
    ui_theme_mode: str = "dark"
    disable_latency: bool = False
    force_errors: dict[str, bool] = field(default_factory=dict)
    last_sync: datetime = field(default_factory=lambda: datetime.now(UTC))


def _seed_users() -> dict[str, MockUser]:
    now = datetime.now(UTC)
    users = [
        MockUser(
            id="usr_1001",
            first_name="Alice",
            last_name="Martin",
            email="alice@cryptobot.dev",
            password="Passw0rd!",
            role=UserRole.USER,
            status=UserStatus.ENABLED,
            created_at=now - timedelta(days=110),
            last_login=now - timedelta(hours=3),
            exchange_configured=True,
        ),
        MockUser(
            id="usr_9001",
            first_name="Admin",
            last_name="Root",
            email="admin@cryptobot.dev",
            password="Admin123!",
            role=UserRole.ADMIN,
            status=UserStatus.ENABLED,
            created_at=now - timedelta(days=300),
            last_login=now - timedelta(minutes=40),
            exchange_configured=True,
        ),
    ]
    return {user.email.lower(): user for user in users}


def _seed_bots() -> dict[str, BotInfo]:
    now = datetime.now(UTC)
    bots = [
        BotInfo(
            id="bot_btc_scalp",
            name="BTC Scalp Prime",
            strategy="Mean Reversion",
            mode_live=True,
            status=BotRuntimeStatus.RUNNING,
            heartbeat_at=now - timedelta(seconds=14),
            last_action_result="Demarrage ok",
            last_action_at=now - timedelta(hours=1),
        ),
        BotInfo(
            id="bot_eth_swing",
            name="ETH Swing Core",
            strategy="Breakout",
            mode_live=False,
            status=BotRuntimeStatus.PAUSED,
            heartbeat_at=now - timedelta(minutes=4),
            last_action_result="Pause manuelle",
            last_action_at=now - timedelta(hours=2),
        ),
        BotInfo(
            id="bot_sol_trend",
            name="SOL Trend Pilot",
            strategy="Trend Following",
            mode_live=True,
            status=BotRuntimeStatus.STOPPED,
            heartbeat_at=now - timedelta(minutes=14),
            last_action_result="Arret securise",
            last_action_at=now - timedelta(days=1),
        ),
    ]
    return {bot.id: bot for bot in bots}


def _seed_bot_templates() -> dict[str, BotTemplate]:
    templates = [
        BotTemplate(
            id="tpl_ai_rsi_btcusdt_1h",
            name="AI RSI Mean Reversion BTCUSDC 1h",
            description="Bot Spot Testnet cle en main combinant regime IA et RSI mean reversion.",
            model_type="regime_classifier_v1",
            strategy_type="rsi_reversal",
            symbol="BTCUSDC",
            timeframe="1h",
            signal_source="regime_classifier_v1+rsi_reversal",
            execution_params={
                "rsi_period": 14,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
                "confirmation_bars": 1,
            },
            risk_limits={
                "risk_per_trade_pct": 1.0,
                "stop_loss_pct": 2.0,
                "take_profit_pct": 4.0,
                "max_open_orders": 1,
                "max_daily_loss_pct": 3.0,
            },
            order_policy={
                "order_type": "MARKET",
                "quote_order_quantity": "100",
                "quote_asset": "USDC",
                "cooldown_seconds": 3600,
            },
        ),
        BotTemplate(
            id="tpl_ai_trend_ethusdt_4h",
            name="AI Trend Following ETHUSDC 4h",
            description="Bot Spot Testnet cle en main combinant regime IA et suivi de tendance.",
            model_type="trend_classifier_v1",
            strategy_type="moving_average_crossover",
            symbol="ETHUSDC",
            timeframe="4h",
            signal_source="trend_classifier_v1+moving_average_crossover",
            execution_params={
                "fast_period": 10,
                "slow_period": 30,
                "confirmation_bars": 2,
            },
            risk_limits={
                "risk_per_trade_pct": 0.75,
                "stop_loss_pct": 2.5,
                "take_profit_pct": 5.0,
                "max_open_orders": 1,
                "max_daily_loss_pct": 2.5,
            },
            order_policy={
                "order_type": "MARKET",
                "quote_order_quantity": "75",
                "quote_asset": "USDC",
                "cooldown_seconds": 14400,
            },
        ),
    ]
    return {template.id: template for template in templates}


def create_mock_store(disable_latency: bool = False) -> MockStore:
    return MockStore(
        users=_seed_users(),
        bots=_seed_bots(),
        bot_templates=_seed_bot_templates(),
        user_bot_selections={},
        binance_credentials={
            "alice@cryptobot.dev": ("AK_TEST_ALICE_1234", "AS_TEST_ALICE_9876"),
            "admin@cryptobot.dev": ("AK_TEST_ADMIN_5678", "AS_TEST_ADMIN_4321"),
        },
        credential_updated_at={
            "alice@cryptobot.dev": datetime.now(UTC) - timedelta(days=4),
            "admin@cryptobot.dev": datetime.now(UTC) - timedelta(days=11),
        },
        disable_latency=disable_latency,
    )
