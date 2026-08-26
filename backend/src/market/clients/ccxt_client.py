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

        return getattr(ccxt, self._ccxt_id)(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                # Bot Spot uniquement : evite que ccxt charge aussi les marches futures/inverse
                # au demarrage (options.fetchMarkets par defaut de binance). En sandbox, le
                # testnet futures (testnet.binancefuture.com) est un systeme distinct du testnet
                # spot (testnet.binance.vision) et son indisponibilite fait echouer
                # load_markets() pour TOUS les types, spot y compris.
                "options": {"defaultType": "spot", "fetchMarkets": ["spot"]},
            }
        )

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
        quantity: Decimal | None = None,
        price: Decimal | None = None,
        quote_quantity: Decimal | None = None,
    ) -> OrderResult:
        native_symbol = CcxtDriver.to_native_symbol(symbol)
        params = {"validate": True} if self._validate_only else {}

        if quote_quantity is not None:
            if quantity is not None:
                raise ValueError("quantity et quote_quantity sont mutuellement exclusifs")
            if side.lower() != "buy" or order_type.lower() != "market":
                raise ValueError("quote_quantity n'est supporte que pour les ordres MARKET BUY")
            # Methode unifiee ccxt : depense un montant en devise de cotation plutot qu'une
            # quantite d'actif de base -- leve NotSupported proprement si l'exchange ne gere
            # pas ce mode (cf. self._client.has['createMarketBuyOrderWithCost']).
            raw = self._client.create_market_buy_order_with_cost(native_symbol, float(quote_quantity), params)
            return self._to_order_result(symbol, raw)

        if quantity is None:
            raise ValueError("quantity est requis quand quote_quantity n'est pas fourni")
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

    def get_open_orders(self, symbol: str | None = None) -> list[OrderResult]:
        native_symbol = CcxtDriver.to_native_symbol(symbol) if symbol else None
        raw_orders = self._client.fetch_open_orders(native_symbol)
        return [self._to_order_result(symbol or self._from_native_symbol(raw), raw) for raw in raw_orders]

    @staticmethod
    def _from_native_symbol(raw: dict) -> str:
        native_symbol = str(raw.get("symbol", ""))
        return native_symbol.replace("/", "")

    def _to_order_result(self, symbol: str, raw: dict) -> OrderResult:
        # Pour un ordre MARKET, "price" (prix limite demande) est souvent absent ou non
        # representatif -- "average" (prix moyen reellement execute) est la source fiable
        # quand disponible. "filled" (quantite reellement executee) prime sur "amount"
        # (quantite demandee) pour la meme raison, notamment avec quote_quantity ou
        # "amount" ne correspond a rien de significatif cote reponse.
        filled = raw.get("filled")
        quantity = filled if filled not in (None, 0) else raw.get("amount", "0")
        executed_price = raw.get("average") if raw.get("average") is not None else raw.get("price")
        return OrderResult(
            order_id=str(raw.get("id")),
            symbol=symbol,
            side=raw.get("side", ""),
            order_type=raw.get("type", ""),
            status=raw.get("status", "unknown"),
            quantity=Decimal(str(quantity)),
            price=Decimal(str(executed_price)) if executed_price is not None else None,
        )
