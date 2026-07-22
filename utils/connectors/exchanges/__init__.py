"""Drivers de données de marché multi-exchange (public, sans clés API).

Expose une interface commune (:class:`MarketDataDriver`) et un normaliseur OHLCV
(:func:`normalize_ohlcv`) partagés par tous les drivers (binance natif, ccxt, …).

Ce package ne dépend d'aucune couche applicative (backend) : les exchanges sont
identifiés par des chaînes (cf. l'enum ``Exchange`` côté backend, par convention).
"""

from __future__ import annotations

from .base import MarketDataDriver, interval_to_timedelta, normalize_ohlcv
from .registry import get_market_data_driver

__all__ = [
    "MarketDataDriver",
    "get_market_data_driver",
    "interval_to_timedelta",
    "normalize_ohlcv",
]
