"""
Market data service for handling market data operations.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MarketDataService:
    """
    Service for handling market data operations.

    In a real implementation, this would connect to external APIs
    like Binance, fetch real market data, and handle caching.
    For now, it provides simulated data for testing.
    """

    def __init__(self):
        self.data_cache = {}

    async def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Get historical market data.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDC')
            timeframe: Timeframe (e.g., '1h', '4h', '1d')
            start_date: Start date
            end_date: End date
            limit: Maximum number of records

        Returns:
            DataFrame with OHLCV data
        """
        logger.info(f"Getting historical data for {symbol} ({timeframe}) from {start_date} to {end_date}")

        # For testing, generate simulated data
        return self._generate_simulated_data(symbol, timeframe, start_date, end_date, limit)

    async def get_latest_data(self, symbol: str, timeframe: str, periods: int = 100) -> pd.DataFrame:
        """
        Get latest market data.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            periods: Number of periods to fetch

        Returns:
            DataFrame with OHLCV data
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=periods)
        return await self.get_historical_data(symbol, timeframe, start_date, end_date, periods)

    def _generate_simulated_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Generate simulated OHLCV data for testing."""
        # Calculate time delta based on timeframe
        timeframe_deltas = {
            "1m": timedelta(minutes=1),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1d": timedelta(days=1),
        }

        delta = timeframe_deltas.get(timeframe, timedelta(hours=1))

        # Generate timestamps
        timestamps = []
        current = start_date
        while current <= end_date:
            timestamps.append(current)
            current += delta
            if limit and len(timestamps) >= limit:
                break

        # Generate price data (random walk)
        base_price = 45000.0  # Starting price
        volatility = 0.02
        rng = np.random.default_rng()

        prices = [base_price]
        for _ in range(len(timestamps) - 1):
            change = rng.normal(0, volatility)
            new_price = prices[-1] * (1 + change)
            prices.append(new_price)

        # Generate OHLCV data
        data = []
        for i, ts in enumerate(timestamps):
            open_price = prices[i]
            close_price = prices[i] * (1 + rng.normal(0, volatility * 0.5))
            high_price = max(open_price, close_price) * (1 + abs(rng.normal(0, volatility * 0.3)))
            low_price = min(open_price, close_price) * (1 - abs(rng.normal(0, volatility * 0.3)))
            volume = rng.uniform(100, 1000)

            data.append(
                {
                    "timestamp": ts,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                }
            )

        return pd.DataFrame(data)

    async def get_available_symbols(self) -> list[str]:
        """Get list of available trading symbols."""
        # In production, this would query the exchange API
        return [
            "BTCUSDC",
            "ETHUSDC",
            "BNBUSDC",
            "ADAUSDC",
            "DOGEUSDC",
            "XRPUSDC",
            "DOTUSDC",
            "UNIUSDC",
            "LTCUSDC",
            "LINKUSDC",
            "SOLUSDC",
            "MATICUSDC",
            "AVAXUSDC",
            "SHIBUSDC",
            "ATOMUSDC",
        ]

    async def get_symbol_info(self, symbol: str) -> dict[str, Any]:
        """Get detailed information about a symbol."""
        # In production, this would query the exchange API
        base_asset = symbol[:-4] if len(symbol) > 4 else symbol[:3]
        quote_asset = symbol[-4:] if len(symbol) > 4 else "USDC"

        return {
            "symbol": symbol,
            "base_asset": base_asset,
            "quote_asset": quote_asset,
            "status": "TRADING",
            "base_precision": 8,
            "quote_precision": 8,
            "min_qty": Decimal("0.00000001"),
            "max_qty": Decimal("9000000.00000000"),
            "step_size": Decimal("0.00000001"),
            "min_price": Decimal("0.01000000"),
            "max_price": Decimal("1000000.00000000"),
            "tick_size": Decimal("0.01000000"),
            "min_notional": Decimal("10.00000000"),
        }

    async def validate_symbol(self, symbol: str) -> bool:
        """Validate if a symbol is available."""
        available_symbols = await self.get_available_symbols()
        return symbol.upper() in available_symbols


# Global market data service instance
market_data_service = MarketDataService()
