"""Schemas bot Spot (controle + catalogue preconfigure)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from schemas.common import BotRuntimeStatus


class BotInfo(BaseModel):
    id: str
    name: str
    strategy: str
    exchange: str = "-"
    mode_live: bool
    mode_label: str = "PAPER"
    status: BotRuntimeStatus
    heartbeat_at: datetime
    last_action_result: str
    last_action_at: datetime
    model_source_label: str = "Moteur déterministe"
    registry_source_label: str = "-"
    model_name: str = "-"
    model_version: str = "-"
    last_signal: str = "-"
    quote_order_quantity: float | None = None
    quote_asset: str = "-"


class BotActionResult(BaseModel):
    success: bool
    message: str
    bot: BotInfo | None = None


class BotConfig(BaseModel):
    bot_id: str
    version: int = 1
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    strategy: str
    base_asset: str
    quote_asset: str = "USDC"
    budget_usdc: float
    max_open_positions: int
    risk_per_trade_pct: float
    take_profit_pct: float
    stop_loss_pct: float
    cooldown_seconds: int
    enabled: bool = True


class BotConfigUpdate(BaseModel):
    strategy: str
    budget_usdc: float
    max_open_positions: int
    risk_per_trade_pct: float
    take_profit_pct: float
    stop_loss_pct: float
    cooldown_seconds: int


class BotTemplate(BaseModel):
    id: str
    name: str
    description: str
    model_type: str
    strategy_type: str
    exchange: str = "-"
    symbol: str
    timeframe: str
    signal_source: str
    execution_params: dict[str, object]
    risk_limits: dict[str, object]
    order_policy: dict[str, object]
    version: str = "1.0"
    status: str = "published"


class UserBotSelection(BaseModel):
    id: str
    template_id: str
    user_email: str
    status: BotRuntimeStatus = BotRuntimeStatus.STOPPED
    auto_trade_enabled: bool = False
    config_snapshot: dict[str, object]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
