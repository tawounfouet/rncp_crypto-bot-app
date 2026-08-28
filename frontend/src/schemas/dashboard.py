"""Schemas tableau de bord (vue d'ensemble agregee)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DashboardBotRow(BaseModel):
    bot_id: str
    name: str
    strategy: str
    exchange: str = "-"
    mode_live: bool
    status: str
    pnl_usdc: float
    roi_pct: float
    fees_usdc: float
    last_signal_at: datetime
    last_action_result: str


class DashboardOverview(BaseModel):
    period_days: int
    total_bots: int
    active_bots: int
    pnl_usdc: float
    avg_roi_pct: float
    fees_usdc: float
    bots: list[DashboardBotRow] = Field(default_factory=list)
