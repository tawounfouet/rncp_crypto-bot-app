"""Schemas bot Spot (controle + catalogue preconfigure)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from schemas.common import BotRuntimeStatus


class BotInfo(BaseModel):
    id: str
    name: str
    strategy: str
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


class BotActionResult(BaseModel):
    success: bool
    message: str
    bot: BotInfo | None = None


class BotTemplate(BaseModel):
    id: str
    name: str
    description: str
    model_type: str
    strategy_type: str
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
