"""Registry des clients d'execution par exchange (issue #13).

Contrairement a utils/connectors/exchanges/registry.py (donnees de marche, Binance natif par
defaut), le cote execution retient ccxt par defaut pour tous les exchanges : c'est la trappe
native qui est l'exception, a activer au cas par cas si ccxt gere mal une operation
(cf. BinanceNativeClient, actuellement disponible mais non enregistre ci-dessous).
"""

from __future__ import annotations

from .base import ExchangeClient
from .ccxt_client import CcxtClient

_NATIVE_CLIENTS: dict[str, type[ExchangeClient]] = {}


def get_exchange_client(exchange: str, api_key: str, api_secret: str, sandbox: bool = False) -> ExchangeClient:
    """Retourne le client d'execution pour un exchange.

    Trappe native si enregistree dans _NATIVE_CLIENTS, sinon client ccxt generique.
    `sandbox` : mode simule -- active le testnet ccxt si l'exchange en a un, sinon retombe
    sur `validate=true` a l'execution des ordres (cf. CcxtClient, docs/testnet-simulation-modes.md).
    """
    exchange = exchange.lower()
    native_cls = _NATIVE_CLIENTS.get(exchange)
    if native_cls is not None:
        return native_cls(api_key=api_key, api_secret=api_secret)
    return CcxtClient(exchange, api_key=api_key, api_secret=api_secret, sandbox=sandbox)
