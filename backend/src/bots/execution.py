"""Passerelle d'execution pour les bots -- couche multi-exchange (issue #13),
pas le Binance Testnet lab (market/binance_testnet_service.py, feature separee).

Expose la meme interface que l'ancien BinanceTestnetService (klines, ticker, symbol_info,
open_orders, balances, place_order) pour que BotService n'ait pas a changer sa logique de
lecture des reponses, mais route reellement via market.clients.factory + le registry de
donnees de marche publiques, en respectant le mode actif (live/sandbox) de l'utilisateur
pour l'exchange du bot (cf. auth/models.py::UserSettings.get_active_mode).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from auth.models import UserSettings
from fastapi import HTTPException, status
from market.clients.base import ExchangeClient
from market.clients.factory import from_user_settings
from shared.database.connection import get_db_session

from utils.connectors.exchanges.registry import get_market_data_driver


@dataclass
class BotOrderRequest:
    """Requete d'ordre independante du Testnet lab (remplace BinanceTestnetOrderRequest)."""

    symbol: str
    side: str
    order_type: str
    quantity: Decimal | None = None
    quote_order_quantity: Decimal | None = None
    price: Decimal | None = None
    client_order_id: str | None = None


class MultiExchangeBotGateway:
    """Passerelle bots -> market.clients (execution reelle) + donnees de marche publiques."""

    def _settings(self, session, user_id: str) -> UserSettings:
        settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not settings:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exchange credentials are not configured for this user.",
            )
        return settings

    def _client(self, user_id: str, exchange: str) -> ExchangeClient:
        with get_db_session() as session:
            settings = self._settings(session, user_id)
            try:
                return from_user_settings(settings, exchange)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # --- Donnees de marche publiques (pas d'authentification requise) ---------------------

    def klines(self, symbol: str, interval: str, *, limit: int = 120, exchange: str = "binance") -> list[dict]:
        driver = get_market_data_driver(exchange)
        return driver.fetch_klines(symbol, interval, limit=limit)

    def ticker(self, symbol: str, *, exchange: str = "binance") -> dict[str, Any]:
        # Pas de fetch_ticker dedie cote donnees de marche publiques -- la derniere bougie
        # 1m suffit pour un prix indicatif (mark-to-market non critique, deja tolerant a
        # l'echec cote appelant, cf. BotService._ticker_price).
        klines = self.klines(symbol, "1m", limit=1, exchange=exchange)
        if not klines:
            return {}
        return {"lastPrice": str(klines[-1]["close"])}

    def symbol_info(self, symbol: str, *, exchange: str = "binance") -> dict[str, Any]:
        import ccxt  # import paresseux, comme le reste de la couche execution

        from utils.connectors.exchanges.ccxt_driver import CCXT_IDS

        native_symbol = _to_native_symbol(symbol)
        client = getattr(ccxt, CCXT_IDS.get(exchange.lower(), exchange.lower()))({"enableRateLimit": True})
        market = client.market(native_symbol)
        active = bool(market.get("active", True))
        return {"status": "TRADING" if active else "BREAK", "isSpotTradingAllowed": active}

    # --- Execution authentifiee, par utilisateur -------------------------------------------

    def open_orders(self, user_id: str, symbol: str, *, exchange: str = "binance") -> list[Any]:
        client = self._client(user_id, exchange)
        return client.get_open_orders(symbol)

    def balances(self, user_id: str, *, non_zero: bool = True, exchange: str = "binance") -> list[dict[str, Any]]:
        client = self._client(user_id, exchange)
        balances = client.get_balances()  # deja filtre aux soldes non nuls par les clients
        return [{"asset": b.asset, "free": str(b.free), "locked": str(b.locked)} for b in balances]

    def place_order(self, user_id: str, order: BotOrderRequest, *, exchange: str = "binance") -> dict[str, Any]:
        client = self._client(user_id, exchange)
        result = client.place_order(
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            quote_quantity=order.quote_order_quantity,
        )
        # Reponse synthetique au format attendu par BotService._record_order /
        # _normalised_fills (pas de detail de fills/commission individuels -- OrderResult
        # ne les porte pas, cf. market/clients/base.py). Un seul "fill" reconstitue a partir
        # de la quantite/prix moyen executes.
        return {
            "status": result.status,
            "orderId": result.order_id,
            "clientOrderId": order.client_order_id,
            "executedQty": str(result.quantity),
            "cummulativeQuoteQty": str(result.quantity * result.price) if result.price is not None else "0",
        }


def _to_native_symbol(symbol: str) -> str:
    from utils.connectors.exchanges.ccxt_driver import CcxtDriver

    return CcxtDriver.to_native_symbol(symbol)
