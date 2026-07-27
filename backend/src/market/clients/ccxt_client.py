"""Client d'execution generique base sur ccxt (comptes, ordres)."""

from __future__ import annotations

import logging
from decimal import Decimal

from utils.connectors.exchanges.ccxt_driver import CCXT_IDS, CcxtDriver

from .base import Balance, ExchangeClient, OrderResult, Ticker

logger = logging.getLogger(__name__)


class CcxtClient(ExchangeClient):
    """Client d'execution pour tout exchange supporte par ccxt."""

    def __init__(self, exchange: str, api_key: str, api_secret: str, sandbox: bool = False):
        self.source = exchange
        self._ccxt_id = CCXT_IDS.get(exchange, exchange)
        self._client = self._build_client(api_key, api_secret)

        # Deux mecanismes selon ce que l'exchange permet reellement (cf.
        # docs/testnet-simulation-modes.md) : bascule sur l'URL testnet si possible, sinon
        # le mode "sandbox" se traduit uniquement par validate=true au moment de l'ordre
        # (cf. _order_params). Jamais les deux, jamais une erreur si l'exchange n'a pas de
        # testnet -- c'est un cas normal (Kraken), pas une mauvaise configuration.
        self._validate_only = False
        if sandbox:
            # cf. utils/connectors/exchanges/registry.py::supports_sandbox_credentials : la cle
            # "test" peut exister avec une valeur None (ex. Kraken) -- il faut verifier la
            # valeur, pas juste la presence de la cle, sinon set_sandbox_mode() plante.
            if self._client.urls.get("test") is not None:
                self._client.set_sandbox_mode(True)
            else:
                self._validate_only = True

    def _build_client(self, api_key: str, api_secret: str):
        import ccxt  # import paresseux : les modules qui n'executent pas d'ordres n'ont pas besoin de ccxt

        return getattr(ccxt, self._ccxt_id)({"apiKey": api_key, "secret": api_secret, "enableRateLimit": True})

    def get_balances(self) -> list[Balance]:
        raw = self._client.fetch_balance()
        free = raw.get("free", {}) or {}
        used = raw.get("used", {}) or {}
        balances = []
        for asset in set(free) | set(used):
            asset_free = Decimal(str(free.get(asset) or 0))
            asset_locked = Decimal(str(used.get(asset) or 0))
            if asset_free > 0 or asset_locked > 0:
                balances.append(Balance(asset=asset, free=asset_free, locked=asset_locked))
        return balances

    def get_tickers(self, quote: str | None = None) -> list[Ticker]:
        raw = self._client.fetch_tickers()
        tickers = []
        for native_symbol, data in raw.items():
            base, sep, tick_quote = native_symbol.partition("/")
            if not sep:
                continue
            if quote and tick_quote != quote:
                continue
            price = data.get("last")
            if price is None:
                continue
            tickers.append(Ticker(symbol=f"{base}{tick_quote}", price=Decimal(str(price))))
        return tickers

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> OrderResult:
        native_symbol = CcxtDriver.to_native_symbol(symbol)
        params = {"validate": True} if self._validate_only else {}
        raw = self._client.create_order(
            native_symbol,
            order_type.lower(),
            side.lower(),
            float(quantity),
            float(price) if price is not None else None,
            params,
        )
        return self._to_order_result(symbol, raw)

    def cancel_order(self, symbol: str, order_id: str) -> OrderResult:
        native_symbol = CcxtDriver.to_native_symbol(symbol)
        raw = self._client.cancel_order(order_id, native_symbol)
        return self._to_order_result(symbol, raw)

    def _to_order_result(self, symbol: str, raw: dict) -> OrderResult:
        return OrderResult(
            order_id=str(raw.get("id")),
            symbol=symbol,
            side=raw.get("side", ""),
            order_type=raw.get("type", ""),
            status=raw.get("status", "unknown"),
            quantity=Decimal(str(raw.get("amount", "0"))),
            price=Decimal(str(raw["price"])) if raw.get("price") is not None else None,
        )
