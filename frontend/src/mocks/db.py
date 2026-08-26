"""Base de donnees mockee en memoire."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from mocks.scenarios import MockScenario
from schemas.auth import MockUser
from schemas.bot import BotConfig, BotInfo
from schemas.common import BotRuntimeStatus, UserRole, UserStatus

SEED = 42


@dataclass
class MockStore:
    users: dict[str, MockUser]
    bots: dict[str, BotInfo]
    bot_configs: dict[str, BotConfig]
    exchange_credentials: dict[str, tuple[str, str]]
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


def _seed_configs() -> dict[str, BotConfig]:
    now = datetime.now(UTC)
    cfgs = [
        BotConfig(
            bot_id="bot_btc_scalp",
            version=4,
            updated_at=now - timedelta(days=2),
            strategy="Mean Reversion",
            base_asset="BTC",
            quote_asset="USDC",
            budget_usdc=6500.0,
            max_open_positions=3,
            risk_per_trade_pct=1.2,
            take_profit_pct=2.7,
            stop_loss_pct=1.6,
            cooldown_seconds=120,
            enabled=True,
        ),
        BotConfig(
            bot_id="bot_eth_swing",
            version=2,
            updated_at=now - timedelta(days=5),
            strategy="Breakout",
            base_asset="ETH",
            quote_asset="USDC",
            budget_usdc=3200.0,
            max_open_positions=2,
            risk_per_trade_pct=1.0,
            take_profit_pct=4.5,
            stop_loss_pct=2.1,
            cooldown_seconds=240,
            enabled=True,
        ),
        BotConfig(
            bot_id="bot_sol_trend",
            version=1,
            updated_at=now - timedelta(days=8),
            strategy="Trend Following",
            base_asset="SOL",
            quote_asset="USDC",
            budget_usdc=2100.0,
            max_open_positions=2,
            risk_per_trade_pct=0.9,
            take_profit_pct=5.5,
            stop_loss_pct=2.7,
            cooldown_seconds=300,
            enabled=False,
        ),
    ]
    return {config.bot_id: config for config in cfgs}


def create_mock_store(disable_latency: bool = False) -> MockStore:
    return MockStore(
        users=_seed_users(),
        bots=_seed_bots(),
        bot_configs=_seed_configs(),
        exchange_credentials={
            "alice@cryptobot.dev": ("AK_TEST_ALICE_1234", "AS_TEST_ALICE_9876"),
            "admin@cryptobot.dev": ("AK_TEST_ADMIN_5678", "AS_TEST_ADMIN_4321"),
        },
        credential_updated_at={
            "alice@cryptobot.dev": datetime.now(UTC) - timedelta(days=4),
            "admin@cryptobot.dev": datetime.now(UTC) - timedelta(days=11),
        },
        disable_latency=disable_latency,
    )
