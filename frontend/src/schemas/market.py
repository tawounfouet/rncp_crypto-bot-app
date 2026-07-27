"""Schemas marché public (prix, sans authentification)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ExchangeOption(BaseModel):
    id: str
    label: str


class PublicPrice(BaseModel):
    symbol: str
    exchange: str
    price: float
    as_of: datetime


class PublicKline(BaseModel):
    symbol: str
    exchange: str
    interval: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
