from __future__ import annotations

import logging
import os
from typing import Any

import requests

from .base import normalize_ohlcv

logger = logging.getLogger(__name__)

BINANCE_BASE_URL = os.environ.get("BINANCE_BASE_URL", "https://api.binance.com")
BINANCE_REQUEST_TIMEOUT = int(os.environ.get("BINANCE_REQUEST_TIMEOUT", "20"))


def map_kline(symbol, interval, raw):
    return normalize_ohlcv(
        symbol=symbol,
        interval=interval,
        source="binance",
        open_time_ms=raw[0],
        open=raw[1],
        high=raw[2],
        low=raw[3],
        close=raw[4],
        volume=raw[5],
        close_time_ms=raw[6],
        quote_asset_volume=raw[7],
        number_of_trades=raw[8],
        taker_buy_base_volume=raw[9],
        taker_buy_quote_volume=raw[10],
    )


def fetch_klines(
    symbol: str,
    interval: str,
    limit: int = 1000,
    start_time_ms: int | None = None,
    end_time_ms: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch klines from the public Binance REST API (no API key required).

    Args:
        symbol: Trading pair (e.g. ``BTCUSDC``)
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
        raise RuntimeError(f"Binance request failed symbol={symbol.upper()} interval={interval}: {resp.text}") from exc

    rows = [map_kline(symbol, interval, k) for k in resp.json()]
    logger.info("Fetched %d klines symbol=%s interval=%s", len(rows), symbol.upper(), interval)
    return rows


class BinanceMarketDataDriver:
    """Binance market data driver using the public REST API (no API key required)."""

    source = "binance"

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 1000,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        return fetch_klines(symbol, interval, limit, start_time_ms, end_time_ms)
