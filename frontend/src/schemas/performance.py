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
