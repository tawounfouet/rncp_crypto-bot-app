from __future__ import annotations

from .base import MarketDataDriver
from .binance_native import BinanceMarketDataDriver
from .ccxt_driver import CCXT_IDS, CcxtDriver

# Drivers natifs (échappatoire quand ccxt ne suffit pas / payload plus riche)
_NATIVE_DRIVERS = {
    "binance": BinanceMarketDataDriver,
}

# Paires tradees par l'app, source unique de verite (remplace a terme les listes dupliquees
# dans backend/src/market/router.py, orchestration/dags/*.py). L'ordre compte : le premier
# element sert de paire par defaut partout ou une paire n'est pas explicitement fournie
# (cf. list_configured_symbols()).
SUPPORTED_SYMBOLS = ["BTCUSDC", "ETHUSDC"]


def get_market_data_driver(exchange: str) -> MarketDataDriver:
    """Retourne le driver de données de marché pour un exchange.

    Driver natif si enregistré, sinon driver ccxt générique.
    """
    exchange = exchange.lower()
    native_cls = _NATIVE_DRIVERS.get(exchange)
    if native_cls is not None:
        return native_cls()
    return CcxtDriver(exchange)


def list_configured_exchanges() -> list[str]:
    """Exchanges pour lesquels un driver de données de marché est réellement résolvable.

    Source unique de vérité : l'union des ids ccxt mappés (CCXT_IDS) et des drivers natifs
    enregistrés. Pas de catalogue distinct à maintenir côté API/frontend.
    """
    return sorted(set(CCXT_IDS) | set(_NATIVE_DRIVERS))


def list_configured_symbols() -> list[str]:
    """Paires tradees par l'app. list_configured_symbols()[0] est la paire par defaut."""
    return list(SUPPORTED_SYMBOLS)


def supports_sandbox_credentials(exchange: str) -> bool:
    """Indique si l'exchange a un vrai testnet/sandbox pilotable via ccxt (set_sandbox_mode).

    Faux pour un exchange comme Kraken (pas de testnet Spot self-service) : le mode "sandbox"
    y reste proposable côté UI, mais pilote un comportement à l'exécution (validate=true)
    plutôt qu'un second jeu de clés — cf. docs/testnet-simulation-modes.md.
    """
    import ccxt  # import paresseux : évite la dépendance dure pour les usages qui n'en ont pas besoin

    ccxt_id = CCXT_IDS.get(exchange.lower(), exchange.lower())
    if not hasattr(ccxt, ccxt_id):
        return False
    instance = getattr(ccxt, ccxt_id)()
    return instance.urls.get("test") is not None
