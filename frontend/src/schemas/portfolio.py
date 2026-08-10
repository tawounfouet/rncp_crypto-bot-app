"""Schemas portfolio Spot."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SystemStatus(BaseModel):
    backend_ok: bool
    exchange: str = "binance"
    exchange_ok: bool
    last_sync: datetime
    backend_message: str = "Connecte"
    exchange_message: str = "Connecte"


class BalanceRow(BaseModel):
    asset: str
    free: float
    locked: float
    value_usdc: float


class OpenOrder(BaseModel):
    order_id: str
    symbol: str
    side: str
    price: float
    amount: float
    status: str
    created_at: datetime


class SpotTrade(BaseModel):
    trade_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    pnl_realized: float
    fee_usdc: float
    executed_at: datetime


class PortfolioSnapshot(BaseModel):
    system_status: SystemStatus
    total_value_usdc: float
    free_cash_usdc: float
    asset_count: int
    open_order_count: int
    balances: list[BalanceRow] = Field(default_factory=list)
    open_orders: list[OpenOrder] = Field(default_factory=list)
    recent_trades: list[SpotTrade] = Field(default_factory=list)
    note: str | None = None
