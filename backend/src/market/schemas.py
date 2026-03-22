"""
Market data Pydantic schemas for the Crypto Trading Bot application.
Contains schemas for market data, symbols, and price information.
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal

from shared.schemas.common import BaseResponse


# Market Data Schemas
class MarketDataResponse(BaseModel):
    """Market data (OHLCV) response."""

    id: str
    symbol: str
    exchange: str
    interval_timeframe: str
    open_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    close_time: datetime
    quote_asset_volume: Optional[Decimal]
    number_of_trades: Optional[int]
    taker_buy_base_volume: Optional[Decimal]
    taker_buy_quote_volume: Optional[Decimal]
    created_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "BTCUSDT_1h_2024-01-01T00:00:00",
                "symbol": "BTCUSDT",
                "exchange": "binance",
                "interval_timeframe": "1h",
                "open_time": "2024-01-01T00:00:00",
                "open_price": "45000.00",
                "high_price": "45500.00",
                "low_price": "44800.00",
                "close_price": "45200.00",
                "volume": "1234.5678",
                "close_time": "2024-01-01T01:00:00",
                "created_at": "2024-01-01T01:00:00",
            }
        }


class MarketDataRequest(BaseModel):
    """Request for market data."""

    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    interval: str = Field(..., description="Timeframe (e.g., 1h, 4h, 1d)")
    start_time: Optional[datetime] = Field(None, description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time")
    limit: int = Field(100, ge=1, le=1000, description="Number of records")

    class Config:
        json_schema_extra = {"example": {"symbol": "BTCUSDT", "interval": "1h", "limit": 100}}


class PriceInfo(BaseModel):
    """Current price information."""

    symbol: str
    price: Decimal
    price_change: Decimal
    price_change_percent: Decimal
    high_24h: Decimal
    low_24h: Decimal
    volume_24h: Decimal
    timestamp: datetime


class SymbolInfo(BaseModel):
    """Trading symbol information."""

    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    base_precision: int
    quote_precision: int
    min_qty: Decimal
    max_qty: Decimal
    step_size: Decimal
    min_price: Decimal
    max_price: Decimal
    tick_size: Decimal
    min_notional: Decimal


class TradingPair(BaseModel):
    """Trading pair with current market info."""

    symbol: str
    base_asset: str
    quote_asset: str
    current_price: Decimal
    volume_24h: Decimal
    change_24h: Decimal
    change_percent_24h: Decimal
    is_active: bool


# Technical Indicators
class MovingAverageData(BaseModel):
    """Moving average indicator data."""

    timestamp: datetime
    sma_short: Decimal
    sma_long: Decimal
    ema_short: Decimal
    ema_long: Decimal


class RSIData(BaseModel):
    """RSI indicator data."""

    timestamp: datetime
    rsi: Decimal
    rsi_signal: str  # "oversold", "overbought", "neutral"


class BollingerBandsData(BaseModel):
    """Bollinger Bands indicator data."""

    timestamp: datetime
    upper_band: Decimal
    middle_band: Decimal
    lower_band: Decimal
    bandwidth: Decimal
    percent_b: Decimal


class TechnicalIndicators(BaseModel):
    """Collection of technical indicators."""

    symbol: str
    timeframe: str
    timestamp: datetime
    moving_averages: Optional[MovingAverageData] = None
    rsi: Optional[RSIData] = None
    bollinger_bands: Optional[BollingerBandsData] = None


# Market Summary
class MarketSummary(BaseModel):
    """Market summary information."""

    total_symbols: int
    active_symbols: int
    total_volume_24h: Decimal
    top_gainers: List[TradingPair]
    top_losers: List[TradingPair]
    most_active: List[TradingPair]
    last_updated: datetime


# Response Models
class MarketDataListResponse(BaseResponse):
    """Response for market data list."""

    data: List[MarketDataResponse]
    symbol: str
    interval: str
    count: int


class PriceResponse(BaseResponse):
    """Response for price information."""

    price_info: PriceInfo


class SymbolListResponse(BaseResponse):
    """Response for symbol list."""

    symbols: List[SymbolInfo]


class TradingPairListResponse(BaseResponse):
    """Response for trading pair list."""

    pairs: List[TradingPair]


class TechnicalIndicatorsResponse(BaseResponse):
    """Response for technical indicators."""

    indicators: TechnicalIndicators


class MarketSummaryResponse(BaseResponse):
    """Response for market summary."""

    summary: MarketSummary


# Websocket Messages
class PriceUpdateMessage(BaseModel):
    """Real-time price update message."""

    type: str = "price_update"
    symbol: str
    price: Decimal
    change: Decimal
    change_percent: Decimal
    volume: Decimal
    timestamp: datetime


class TradeUpdateMessage(BaseModel):
    """Real-time trade update message."""

    type: str = "trade_update"
    symbol: str
    price: Decimal
    quantity: Decimal
    side: str
    timestamp: datetime


class DepthUpdateMessage(BaseModel):
    """Order book depth update message."""

    type: str = "depth_update"
    symbol: str
    bids: List[List[Decimal]]  # [price, quantity]
    asks: List[List[Decimal]]  # [price, quantity]
    timestamp: datetime
