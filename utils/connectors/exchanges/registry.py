from __future__ import annotations

from .base import MarketDataDriver
from .binance_native import BinanceMarketDataDriver
from .ccxt_driver import CcxtDriver

# Drivers natifs (échappatoire quand ccxt ne suffit pas / payload plus riche)
_NATIVE_DRIVERS = {
    "binance": BinanceMarketDataDriver,
}


def get_market_data_driver(exchange: str) -> MarketDataDriver:
    """Retourne le driver de données de marché pour un exchange.

    Driver natif si enregistré, sinon driver ccxt générique.
    """
    exchange = exchange.lower()
    native_cls = _NATIVE_DRIVERS.get(exchange)
    if native_cls is not None:
        return native_cls()
    return CcxtDriver(exchange)
