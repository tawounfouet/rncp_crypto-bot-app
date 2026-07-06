"""API schemas for immutable bot templates and user bot instances."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BotTemplateStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DISABLED = "disabled"


class UserBotStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class UserBotMode(StrEnum):
    TESTNET = "TESTNET"
    PAPER = "PAPER"


class BotTemplateResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None = None
    model_type: str
    strategy_type: str
    symbol: str
    timeframe: str
    signal_source: str
    exchange: str
    environment: str
    execution_params: dict[str, Any]
    risk_limits: dict[str, Any]
    order_policy: dict[str, Any]
    version: str
    status: BotTemplateStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserBotCreate(BaseModel):
    """Create a user bot by selecting a complete immutable template."""

    bot_template_id: str = Field(..., description="Published bot template identifier")

    model_config = ConfigDict(extra="forbid")


class UserBotResponse(BaseModel):
    id: str
    user_id: str
    bot_template_id: str
    exchange_credential_id: str | None = None
    mode: UserBotMode
    status: UserBotStatus
    auto_trade_enabled: bool
    config_snapshot: dict[str, Any]
    last_decision_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    template: BotTemplateResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class BotRunResponse(BaseModel):
    id: str
    user_bot_instance_id: str
    user_id: str
    started_at: datetime
    ended_at: datetime | None = None
    status: str
    error_message: str | None = None
    worker_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BotOrderResponse(BaseModel):
    id: str
    user_id: str
    user_bot_instance_id: str
    exchange: str
    environment: str
    symbol: str
    side: str
    order_type: str
    quantity: Decimal | None = None
    quote_order_quantity: Decimal | None = None
    price: Decimal | None = None
    status: str
    binance_order_id: str | None = None
    client_order_id: str | None = None
    raw_response: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BotTradeResponse(BaseModel):
    id: str
    user_id: str
    order_id: str
    user_bot_instance_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal | None = None
    fee_asset: str | None = None
    trade_time: datetime
    raw_response: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BotPositionResponse(BaseModel):
    id: str
    user_id: str
    user_bot_instance_id: str
    symbol: str
    quantity: Decimal
    average_entry_price: Decimal | None = None
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BotPerformanceResponse(BaseModel):
    user_bot_instance_id: str
    symbol: str
    status: UserBotStatus
    total_orders: int
    total_trades: int
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    net_position_quantity: Decimal
    average_entry_price: Decimal | None = None
    last_signal: str | None = None
    last_action: str | None = None
    last_decision_at: datetime | None = None


class PerformanceUnavailableReason(BaseModel):
    field: str
    reason: str


class UserPerformanceGlobalResponse(BaseModel):
    capital_initial: Decimal | None = None
    capital_current: Decimal | None = None
    pnl_total: Decimal | None = None
    pnl_realized: Decimal
    pnl_unrealized: Decimal | None = None
    total_orders: int
    total_trades: int
    win_rate_pct: float | None = None


class BotPerformanceContributionResponse(BaseModel):
    bot_id: str
    bot_name: str
    model_name: str | None = None
    model_version: str | None = None
    pnl_total: Decimal | None = None
    pnl_realized: Decimal
    pnl_unrealized: Decimal | None = None
    orders: int
    trades: int
    last_decision: str | None = None
    last_decision_at: datetime | None = None
    last_ai_signal: str | None = None
    average_confidence: float | None = None
    pnl_contribution_pct: float | None = None


class PerformanceDecisionHistoryResponse(BaseModel):
    id: str
    bot_id: str
    bot_name: str
    timestamp: datetime
    model_source: str | None = None
    registry_source: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    confidence: float | None = None
    raw_ai_signal: str | None = None
    deterministic_signal: str | None = None
    final_action: str
    risk_decision: str
    reason: str | None = None


class PerformanceOrderHistoryResponse(BaseModel):
    id: str
    bot_id: str
    bot_name: str
    created_at: datetime
    symbol: str
    side: str
    order_type: str
    status: str
    binance_order_id: str | None = None
    quote_order_quantity: Decimal | None = None
    quantity: Decimal | None = None


class PerformanceTradeHistoryResponse(BaseModel):
    id: str
    bot_id: str
    bot_name: str
    order_id: str
    trade_time: datetime
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal | None = None
    fee_asset: str | None = None
    realized_pnl: Decimal | None = None


class PerformancePnlPointResponse(BaseModel):
    timestamp: datetime
    bot_id: str | None = None
    bot_name: str | None = None
    realized_pnl: Decimal
    cumulative_realized_pnl: Decimal
    capital_current: Decimal | None = None


class UserPerformanceSummaryResponse(BaseModel):
    generated_at: datetime
    period_start: datetime | None = None
    period_end: datetime
    period_days: int
    bot_id: str | None = None
    model_name: str | None = None
    unavailable_reasons: list[PerformanceUnavailableReason] = Field(default_factory=list)
    global_performance: UserPerformanceGlobalResponse
    bots: list[BotPerformanceContributionResponse] = Field(default_factory=list)
    decisions: list[PerformanceDecisionHistoryResponse] = Field(default_factory=list)
    orders: list[PerformanceOrderHistoryResponse] = Field(default_factory=list)
    trades: list[PerformanceTradeHistoryResponse] = Field(default_factory=list)
    pnl_curve: list[PerformancePnlPointResponse] = Field(default_factory=list)


class TradingDecisionResponse(BaseModel):
    id: str
    user_bot_instance_id: str
    run_id: str | None = None
    user_id: str
    timestamp: datetime
    symbol: str
    timeframe: str
    market_snapshot: dict[str, Any] | None = None
    model_output: dict[str, Any] | None = None
    strategy_signal: str
    risk_decision: str
    final_action: str
    reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BotActionResponse(BaseModel):
    success: bool = True
    message: str
    bot: UserBotResponse
