"""Schemas bot Spot (controle + configuration)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from schemas.common import BotRuntimeStatus


class BotInfo(BaseModel):
    id: str
    name: str
    strategy: str
    mode_live: bool
    status: BotRuntimeStatus
    heartbeat_at: datetime
    last_action_result: str
    last_action_at: datetime


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
    quote_asset: str = "USDT"
    budget_usdt: float
    max_open_positions: int
    risk_per_trade_pct: float
    take_profit_pct: float
    stop_loss_pct: float
    cooldown_seconds: int
    enabled: bool = True


class BotConfigUpdate(BaseModel):
    strategy: str
    budget_usdt: float
    max_open_positions: int
    risk_per_trade_pct: float
    take_profit_pct: float
    stop_loss_pct: float
    cooldown_seconds: int
