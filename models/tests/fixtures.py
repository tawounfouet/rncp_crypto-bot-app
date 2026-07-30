"""Shared test fixtures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd


def sample_ohlcv(rows: int = 80) -> pd.DataFrame:
    """Create deterministic OHLCV data for tests."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    records = []
    price = 100.0
    for index in range(rows):
        open_price = price
        close_price = price * (1 + (0.003 if index % 3 == 0 else -0.001))
        high = max(open_price, close_price) + 1.0
        low = min(open_price, close_price) - 1.0
        records.append(
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "open_time": start + timedelta(hours=index),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close_price,
                "volume": 1000 + index,
                "close_time": start + timedelta(hours=index, minutes=59),
                "quote_asset_volume": (1000 + index) * close_price,
                "number_of_trades": 100 + index,
                "taker_buy_base_volume": (1000 + index) * 0.5,
                "taker_buy_quote_volume": (1000 + index) * close_price * 0.5,
                "source": "fixture",
            }
        )
        price = close_price
    return pd.DataFrame(records)
