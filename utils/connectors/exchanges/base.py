from datetime import UTC, datetime, timedelta
from typing import Any, Protocol


def _ms_to_utc(value: int | str) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


def interval_to_timedelta(interval: str) -> timedelta:
    """Convert a Binance interval string to a timedelta object.

    Args:
        interval: Binance interval string (e.g. ``1m``, ``5m``,``1h``, ``1d``, ``1w``)

    Returns:
        Corresponding timedelta object.

    Raises:
        ValueError: If the interval string is invalid.
    """
    unit = interval[-1]
    value = int(interval[:-1])
    if unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    elif unit == "w":
        return timedelta(weeks=value)
    else:
        raise ValueError(f"Invalid interval: {interval}")


def normalize_ohlcv(
    *,
    symbol,
    interval,
    source,
    open_time_ms,
    open,
    high,
    low,
    close,
    volume,
    close_time_ms=None,
    quote_asset_volume=None,
    number_of_trades=None,
    taker_buy_base_volume=None,
    taker_buy_quote_volume=None,
) -> dict:
    """Normalize OHLCV data from various sources into a standard dictionary format.

    Args:
        symbol: Trading pair (e.g. ``BTCUSDT``)
        interval: Kline interval (e.g. ``1h``, ``4h``, ``1d``)
        source: Data source (e.g. ``binance``, ``kraken``, etc.)
        open_time: Open time in datetime
        open: Open price
        high: High price
        low: Low price
        close: Close price
        volume: Volume
        close_time: Close time in datetime (optional)
        quote_asset_volume: Quote asset volume (optional)
        number_of_trades: Number of trades (optional)
        taker_buy_base_volume: Taker buy base volume (optional)
        taker_buy_quote_volume: Taker buy quote volume (optional)
    Returns:
        Normalized OHLCV dictionary.
    """
    open_time = _ms_to_utc(open_time_ms)
    if close_time_ms is not None:
        close_time = _ms_to_utc(close_time_ms)
    else:
        close_time = open_time + interval_to_timedelta(interval) - timedelta(milliseconds=1)

    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "source": source,
        "open_time": open_time,
        "open": float(open),
        "high": float(high),
        "low": float(low),
        "close": float(close),
        "volume": float(volume),
        "close_time": close_time,
        "quote_asset_volume": float(quote_asset_volume) if quote_asset_volume not in (None, "") else None,
        "number_of_trades": int(number_of_trades) if number_of_trades not in (None, "") else None,
        "taker_buy_base_volume": float(taker_buy_base_volume) if taker_buy_base_volume not in (None, "") else None,
        "taker_buy_quote_volume": float(taker_buy_quote_volume) if taker_buy_quote_volume not in (None, "") else None,
    }


class MarketDataDriver(Protocol):
    """Contrat commun à tous les drivers de données de marché."""

    source: str  # ex. "binance", "kraken", "futures", etc.

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 1000,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch klines from the market data source.

        Args:
            symbol: Trading pair (e.g. ``BTCUSDT``)
            interval: Kline interval (e.g. ``1h``, ``4h``, ``1d``)
            limit: Number of klines (max 1000 per call)
            start_time_ms: Start timestamp in milliseconds
            end_time_ms: End timestamp in milliseconds

        Returns:
            List of normalised OHLCV dicts (see :func:`normalize_ohlcv
        Raises:
            RuntimeError: On HTTP or network error.
        """
