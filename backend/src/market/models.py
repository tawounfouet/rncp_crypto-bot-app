"""
Market data models for the Crypto Trading Bot.
Contains MarketData model for OHLCV data storage.
"""

from decimal import Decimal
from datetime import datetime
from sqlalchemy import Column, String, DECIMAL, Integer, DateTime, UniqueConstraint

from shared.models.base import BaseModel, register_model


@register_model
class MarketData(BaseModel):
    """
    Market data model - OHLCV data storage.
    """

    __tablename__ = "market_data"

    # Market identification
    symbol = Column(String(20), nullable=False, index=True)
    exchange = Column(String(50), nullable=False, default="binance", index=True)
    interval_timeframe = Column(String(10), nullable=False, index=True)

    # OHLCV data
    open_time = Column(DateTime, nullable=False, index=True)
    open_price = Column(DECIMAL(20, 8), nullable=False)
    high_price = Column(DECIMAL(20, 8), nullable=False)
    low_price = Column(DECIMAL(20, 8), nullable=False)
    close_price = Column(DECIMAL(20, 8), nullable=False)
    volume = Column(DECIMAL(20, 8), nullable=False)
    close_time = Column(DateTime, nullable=False, index=True)

    # Additional Binance data
    quote_asset_volume = Column(DECIMAL(20, 8), nullable=True)
    number_of_trades = Column(Integer, nullable=True)
    taker_buy_base_volume = Column(DECIMAL(20, 8), nullable=True)
    taker_buy_quote_volume = Column(DECIMAL(20, 8), nullable=True)

    # Constraints to avoid duplicates
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "exchange",
            "interval_timeframe",
            "open_time",
            name="uq_market_data_symbol_time",
        ),
    )

    @property
    def ohlc(self) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        """Get OHLC as tuple."""
        return (self.open_price, self.high_price, self.low_price, self.close_price)

    @property
    def ohlcv(self) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
        """Get OHLCV as tuple."""
        return (
            self.open_price,
            self.high_price,
            self.low_price,
            self.close_price,
            self.volume,
        )

    @property
    def typical_price(self) -> Decimal:
        """Calculate typical price (HLC/3)."""
        return (self.high_price + self.low_price + self.close_price) / 3

    @property
    def weighted_close_price(self) -> Decimal:
        """Calculate weighted close price (OHLC/4)."""
        return (self.open_price + self.high_price + self.low_price + self.close_price) / 4

    @property
    def price_range(self) -> Decimal:
        """Calculate price range (High - Low)."""
        return self.high_price - self.low_price

    @property
    def price_change(self) -> Decimal:
        """Calculate price change (Close - Open)."""
        return self.close_price - self.open_price

    @property
    def price_change_percentage(self) -> float:
        """Calculate price change percentage."""
        if self.open_price == 0:
            return 0.0
        return float((self.price_change / self.open_price) * 100)

    @property
    def body_size(self) -> Decimal:
        """Calculate candlestick body size."""
        return abs(self.close_price - self.open_price)

    @property
    def upper_shadow(self) -> Decimal:
        """Calculate upper shadow size."""
        return self.high_price - max(self.open_price, self.close_price)

    @property
    def lower_shadow(self) -> Decimal:
        """Calculate lower shadow size."""
        return min(self.open_price, self.close_price) - self.low_price

    @property
    def is_bullish(self) -> bool:
        """Check if the candle is bullish (close > open)."""
        return self.close_price > self.open_price

    @property
    def is_bearish(self) -> bool:
        """Check if the candle is bearish (close < open)."""
        return self.close_price < self.open_price

    @property
    def is_doji(self) -> bool:
        """Check if the candle is a doji (open ≈ close)."""
        # Consider it a doji if the body is less than 0.1% of the range
        if self.price_range == 0:
            return True
        body_percentage = (self.body_size / self.price_range) * 100
        return body_percentage < 0.1

    @property
    def volume_weighted_average_price(self) -> Decimal:
        """Calculate VWAP (simplified using typical price)."""
        if self.volume == 0:
            return self.typical_price
        # This is a simplified VWAP calculation for a single candle
        # In practice, VWAP is calculated over multiple periods
        return self.typical_price

    @property
    def timeframe_minutes(self) -> int:
        """Get timeframe in minutes."""
        timeframe_map = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "6h": 360,
            "8h": 480,
            "12h": 720,
            "1d": 1440,
            "3d": 4320,
            "1w": 10080,
            "1M": 43200,  # Approximate
        }
        return timeframe_map.get(self.interval_timeframe, 1)

    def to_dict(self) -> dict:
        """Convert to dictionary format (useful for APIs)."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timeframe": self.interval_timeframe,
            "open_time": self.open_time.isoformat() if self.open_time else None,
            "close_time": self.close_time.isoformat() if self.close_time else None,
            "open": float(self.open_price),
            "high": float(self.high_price),
            "low": float(self.low_price),
            "close": float(self.close_price),
            "volume": float(self.volume),
            "quote_volume": (float(self.quote_asset_volume) if self.quote_asset_volume else None),
            "trades": self.number_of_trades,
            "taker_buy_base_volume": (float(self.taker_buy_base_volume) if self.taker_buy_base_volume else None),
            "taker_buy_quote_volume": (float(self.taker_buy_quote_volume) if self.taker_buy_quote_volume else None),
        }

    @classmethod
    def from_binance_kline(cls, symbol: str, timeframe: str, kline_data: list, exchange: str = "binance"):
        """
        Create MarketData instance from Binance kline data.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            timeframe: Timeframe (e.g., "1h")
            kline_data: Binance kline data list
            exchange: Exchange name

        Returns:
            MarketData: New instance
        """
        return cls(
            symbol=symbol,
            exchange=exchange,
            interval_timeframe=timeframe,
            open_time=datetime.fromtimestamp(kline_data[0] / 1000),
            open_price=Decimal(kline_data[1]),
            high_price=Decimal(kline_data[2]),
            low_price=Decimal(kline_data[3]),
            close_price=Decimal(kline_data[4]),
            volume=Decimal(kline_data[5]),
            close_time=datetime.fromtimestamp(kline_data[6] / 1000),
            quote_asset_volume=Decimal(kline_data[7]) if kline_data[7] else None,
            number_of_trades=int(kline_data[8]) if kline_data[8] else None,
            taker_buy_base_volume=Decimal(kline_data[9]) if kline_data[9] else None,
            taker_buy_quote_volume=Decimal(kline_data[10]) if kline_data[10] else None,
        )

    @classmethod
    def from_ohlcv(
        cls,
        symbol: str,
        timeframe: str,
        timestamp: datetime,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: float,
        exchange: str = "binance",
    ):
        """
        Create MarketData instance from OHLCV data.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            timestamp: Candle timestamp
            open_price: Open price
            high_price: High price
            low_price: Low price
            close_price: Close price
            volume: Volume
            exchange: Exchange name

        Returns:
            MarketData: New instance
        """
        # Calculate close time based on timeframe
        timeframe_minutes = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,
        }.get(timeframe, 1)

        from datetime import timedelta

        close_time = timestamp + timedelta(minutes=timeframe_minutes)

        return cls(
            symbol=symbol,
            exchange=exchange,
            interval_timeframe=timeframe,
            open_time=timestamp,
            close_time=close_time,
            open_price=Decimal(str(open_price)),
            high_price=Decimal(str(high_price)),
            low_price=Decimal(str(low_price)),
            close_price=Decimal(str(close_price)),
            volume=Decimal(str(volume)),
        )

    def __repr__(self) -> str:
        return (
            f"<MarketData(symbol={self.symbol}, timeframe={self.interval_timeframe}, "
            f"open_time={self.open_time}, close={self.close_price})>"
        )
