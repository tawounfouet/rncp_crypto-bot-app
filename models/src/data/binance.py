"""Binance data transformations (post-processing after MinIO load).

The raw OHLCV data is now fetched by ``jobs/ingest/collect_ohlcv.py``
and stored in MinIO.  This module provides symbol-specific transformations
(e.g. price inversion for inverted pairs like ETHBTC → BTCETH).
"""

from __future__ import annotations

import pandas as pd


def apply_symbol_mapping(df: pd.DataFrame, source_symbol: str, invert_price: bool = False) -> pd.DataFrame:
    """Apply symbol mapping transformations (e.g. price inversion).

    Args:
        df: DataFrame with OHLCV data for the source symbol
        source_symbol: Original symbol in the data (e.g. ``ETHBTC``)
        invert_price: If ``True``, invert open/high/low/close prices

    Returns:
        Transformed DataFrame with updated symbol and prices
    """
    result = df.copy()
    if invert_price:
        for col in ["open", "high", "low", "close"]:
            result[col] = 1.0 / result[col]
        result["high"], result["low"] = result["low"], result["high"]
    result["symbol"] = source_symbol.upper()
    return result
