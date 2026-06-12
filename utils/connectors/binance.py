"""Pure functions for Binance data collection — no SDK dependency.

These functions use ``requests`` directly (no ``python-binance`` lib) so they
can be reused from **any** layer (backend, jobs, models) without pulling in
heavy SDK dependencies.

Env vars (all optional):
    BINANCE_BASE_URL         Default: https://api.binance.com
    BINANCE_REQUEST_TIMEOUT  Default: 20
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)

BINANCE_BASE_URL = os.environ.get("BINANCE_BASE_URL", "https://api.binance.com")
BINANCE_REQUEST_TIMEOUT = int(os.environ.get("BINANCE_REQUEST_TIMEOUT", "20"))

#: Columns returned by the ``/api/v3/klines`` endpoint
KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "number_of_trades",
    "taker_buy_base_volume", "taker_buy_quote_volume",
]


def _ms_to_utc(value: int | str) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


def map_kline(symbol: str, interval: str, raw: list[Any]) -> dict[str, Any]:
    """Convert a raw Binance kline array into a normalised OHLCV dict.

    Args:
        symbol: Trading pair (e.g. ``BTCUSDT``)
        interval: Kline interval (e.g. ``1h``, ``4h``, ``1d``)
        raw: Raw 12-element kline array from the Binance REST API.

    Returns:
        Normalised OHLCV dictionary (can be passed to ``pd.DataFrame`` directly).
    """
    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "open_time": _ms_to_utc(raw[0]),
        "open": float(raw[1]),
        "high": float(raw[2]),
        "low": float(raw[3]),
        "close": float(raw[4]),
        "volume": float(raw[5]),
        "close_time": _ms_to_utc(raw[6]),
        "quote_asset_volume": float(raw[7]) if raw[7] not in (None, "") else None,
        "number_of_trades": int(raw[8]) if raw[8] not in (None, "") else None,
        "taker_buy_base_volume": float(raw[9]) if raw[9] not in (None, "") else None,
        "taker_buy_quote_volume": float(raw[10]) if raw[10] not in (None, "") else None,
        "source": "binance",
    }


def fetch_klines(
    symbol: str,
    interval: str,
    limit: int = 1000,
    start_time_ms: int | None = None,
    end_time_ms: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch klines from the public Binance REST API (no API key required).

    Args:
        symbol: Trading pair (e.g. ``BTCUSDT``)
        interval: Kline interval (e.g. ``1h``, ``4h``, ``1d``)
        limit: Number of klines (max 1000 per call)
        start_time_ms: Start timestamp in milliseconds
        end_time_ms: End timestamp in milliseconds

    Returns:
        List of normalised OHLCV dicts (see :func:`map_kline`).

    Raises:
        RuntimeError: On HTTP or network error.
    """
    url = f"{BINANCE_BASE_URL.rstrip('/')}/api/v3/klines"
    params: dict[str, Any] = {
        "symbol": symbol.upper(),
        "interval": interval,
        "limit": limit,
    }
    if start_time_ms is not None:
        params["startTime"] = start_time_ms
    if end_time_ms is not None:
        params["endTime"] = end_time_ms

    logger.info("Fetching klines symbol=%s interval=%s limit=%s", symbol.upper(), interval, limit)
    resp = requests.get(url, params=params, timeout=BINANCE_REQUEST_TIMEOUT)
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"Binance request failed symbol={symbol.upper()} interval={interval}: {resp.text}"
        ) from exc

    rows = [map_kline(symbol, interval, k) for k in resp.json()]
    logger.info("Fetched %d klines symbol=%s interval=%s", len(rows), symbol.upper(), interval)
    return rows
