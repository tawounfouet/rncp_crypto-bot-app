"""Schemas performance Spot."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PerformanceMetrics(BaseModel):
    pnl_realized_usdc: float
    roi_pct: float
    max_drawdown_pct: float
    win_rate_pct: float
    fees_usdc: float


class EquityPoint(BaseModel):
    timestamp: datetime
    equity_usdc: float


class TradeJournalEntry(BaseModel):
    id: str
    bot_id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    pnl_usdc: float
    fee_usdc: float
    duration_min: int
    closed_at: datetime


class PerformanceSnapshot(BaseModel):
    bot_id: str
    period_days: int
    metrics: PerformanceMetrics
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    trade_journal: list[TradeJournalEntry] = Field(default_factory=list)
    scenario_label: str


class PerformanceUnavailableReason(BaseModel):
    field: str
    reason: str


class UserPerformanceGlobal(BaseModel):
    capital_initial: float | None = None
    capital_current: float | None = None
    pnl_total: float | None = None
    pnl_realized: float
    pnl_unrealized: float | None = None
    total_orders: int
    total_trades: int
    win_rate_pct: float | None = None


class BotPerformanceContribution(BaseModel):
    bot_id: str
    bot_name: str
    model_name: str | None = None
    model_version: str | None = None
    pnl_total: float | None = None
    pnl_realized: float
    pnl_unrealized: float | None = None
    orders: int
    trades: int
    last_decision: str | None = None
    last_decision_at: datetime | None = None
    last_ai_signal: str | None = None
    average_confidence: float | None = None
    pnl_contribution_pct: float | None = None


class PerformanceDecisionHistory(BaseModel):
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


class PerformanceOrderHistory(BaseModel):
    id: str
    bot_id: str
    bot_name: str
    created_at: datetime
    symbol: str
    side: str
    order_type: str
    status: str
    binance_order_id: str | None = None
    quote_order_quantity: float | None = None
    quantity: float | None = None


class PerformanceTradeHistory(BaseModel):
    id: str
    bot_id: str
    bot_name: str
    order_id: str
    trade_time: datetime
    symbol: str
    side: str
    quantity: float
    price: float
    fee: float | None = None
    fee_asset: str | None = None
    realized_pnl: float | None = None


class PerformancePnlPoint(BaseModel):
    timestamp: datetime
    bot_id: str | None = None
    bot_name: str | None = None
    realized_pnl: float
    cumulative_realized_pnl: float
    capital_current: float | None = None


class PerformanceDashboard(BaseModel):
    generated_at: datetime
    period_start: datetime | None = None
    period_end: datetime
    period_days: int
    bot_id: str | None = None
    model_name: str | None = None
    unavailable_reasons: list[PerformanceUnavailableReason] = Field(default_factory=list)
    global_performance: UserPerformanceGlobal
    bots: list[BotPerformanceContribution] = Field(default_factory=list)
    decisions: list[PerformanceDecisionHistory] = Field(default_factory=list)
    orders: list[PerformanceOrderHistory] = Field(default_factory=list)
    trades: list[PerformanceTradeHistory] = Field(default_factory=list)
    pnl_curve: list[PerformancePnlPoint] = Field(default_factory=list)
    scenario_label: str = "Backend bots Testnet"
