"""Adaptateur natif Binance : refront de ClientBinance derriere le contrat ExchangeClient.

Trappe optionnelle (cf. registry.py) pour le jour ou ccxt gererait mal une operation Binance ;
tant que ccxt suffit, get_exchange_client() utilise CcxtClient par defaut.
"""

from __future__ import annotations

from decimal import Decimal

from .base import Balance, ExchangeClient, OrderResult, Ticker
from .binance import ClientBinance


class BinanceNativeClient(ExchangeClient):
    """Client d'execution Binance natif (python-binance), normalise au contrat ExchangeClient."""

    source = "binance"

    def __init__(self, api_key: str, api_secret: str):
        self._client = ClientBinance(api_key=api_key, api_secret=api_secret)

    def get_balances(self) -> list[Balance]:
        account_info = self._client.get_account_info() or {}
        balances = []
        for b in account_info.get("balances", []):
            free = Decimal(str(b.get("free", "0")))
            locked = Decimal(str(b.get("locked", "0")))
            if free > 0 or locked > 0:
                balances.append(Balance(asset=b["asset"], free=free, locked=locked))
        return balances

    def get_tickers(self, quote: str | None = None) -> list[Ticker]:
        raw = self._client.get_all_tickers() or []
        tickers = []
        for t in raw:
            symbol = t.get("symbol", "")
            price = t.get("price")
            if price is None or (quote and not symbol.endswith(quote)):
                continue
            tickers.append(Ticker(symbol=symbol, price=Decimal(str(price))))
        return tickers

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> OrderResult:
        raw = self._client.place_order(
            symbol=symbol,
            side=side.upper(),
            order_type=order_type.upper(),
            quantity=float(quantity),
            price=float(price) if price is not None else None,
        )
        return self._to_order_result(symbol, raw or {})

    def cancel_order(self, symbol: str, order_id: str) -> OrderResult:
        raw = self._client.cancel_order(symbol=symbol, order_id=int(order_id))
        return self._to_order_result(symbol, raw or {})

    def _to_order_result(self, symbol: str, raw: dict) -> OrderResult:
        return OrderResult(
            order_id=str(raw.get("orderId", "")),
            symbol=symbol,
            side=raw.get("side", ""),
            order_type=raw.get("type", ""),
            status=raw.get("status", "unknown"),
            quantity=Decimal(str(raw.get("origQty", "0"))),
            price=Decimal(str(raw["price"])) if raw.get("price") not in (None, "") else None,
        )
