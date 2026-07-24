from __future__ import annotations

import logging

from .base import normalize_ohlcv

logger = logging.getLogger(__name__)

# id app -> id ccxt (quand ils diffèrent)
# Partage avec backend/src/market/clients/ccxt_client.py (execution) : meme mapping des deux cotes.
CCXT_IDS = {
    "binance": "binance",
    "binance_us": "binanceus",
    "kraken": "kraken",
    #    "kucoin": "kucoin",
    #    "coinbase": "coinbase",
}

# quotes connues, les plus LONGUES d'abord (USDT avant USD !)
_KNOWN_QUOTES = ["USDT", "USDC", "USD", "EUR", "BTC", "ETH"]


class CcxtDriver:
    """Market data driver using the CCXT library."""

    @staticmethod
    def to_native_symbol(symbol: str) -> str:
        """Convert a symbol to the native exchange format.

        Args:
            symbol: Trading pair (e.g. ``BTCUSDT``)

        Returns:
            Native exchange symbol (e.g. ``BTC/USDT``)
        """
        s = symbol.upper()
        for quote in _KNOWN_QUOTES:
            if s.endswith(quote) and len(s) > len(quote):
                return f"{s[: -len(quote)]}/{quote}"
        raise ValueError(f"Unknown quote in symbol: {symbol}")

    def __init__(self, exchange: str):
        self.source = exchange
        self._ccxt_id = CCXT_IDS.get(exchange, exchange)
        self._client = None  # instancié paresseusement

    def _get_client(self):
        if self._client is None:
            import ccxt  # <-- IMPORT PARESSEUX (dans la méthode, pas en haut)

            self._client = getattr(ccxt, self._ccxt_id)({"enableRateLimit": True})
        return self._client

    def fetch_klines(self, symbol, interval, limit=1000, start_time_ms=None, end_time_ms=None):
        client = self._get_client()
        native = self.to_native_symbol(symbol)  # 'BTC/USDT' pour ccxt
        rows = client.fetch_ohlcv(native, timeframe=interval, since=start_time_ms, limit=limit)
        return [
            normalize_ohlcv(
                symbol=symbol,
                interval=interval,
                source=self.source,  # on garde 'BTCUSDT' canonique
                open_time_ms=r[0],
                open=r[1],
                high=r[2],
                low=r[3],
                close=r[4],
                volume=r[5],
            )
            for r in rows
        ]
