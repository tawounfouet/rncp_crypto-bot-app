"""Tests for bots.execution.MultiExchangeBotGateway -- l'adaptation qui route
l'execution des bots via la couche multi-exchange (market.clients) plutot que via
l'ancien Binance Testnet lab. Zone critique : c'est ce qui determine quel montant
reel est engage sur l'exchange pour le compte de l'utilisateur."""

from __future__ import annotations

import sys
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


def _create_user() -> str:
    from auth.schemas import UserCreate
    from auth.user_service import UserService

    user = UserService().create_user(
        UserCreate(
            email="gateway-user@example.com",
            username="gatewayuser",
            password="SecurePass123!",  # noqa: S106
        )
    )
    return user.id


class TestKlinesAndTicker:
    def test_klines_delegates_to_market_data_driver(self):
        from bots.execution import MultiExchangeBotGateway

        fake_driver = MagicMock()
        fake_driver.fetch_klines.return_value = [{"close": 100.0}]

        with patch("bots.execution.get_market_data_driver", return_value=fake_driver) as get_driver:
            gateway = MultiExchangeBotGateway()
            result = gateway.klines("BTCUSDC", "1h", limit=50, exchange="kraken")

        get_driver.assert_called_once_with("kraken")
        fake_driver.fetch_klines.assert_called_once_with("BTCUSDC", "1h", limit=50)
        assert result == [{"close": 100.0}]

    def test_ticker_returns_last_close_price_from_1m_kline(self):
        from bots.execution import MultiExchangeBotGateway

        gateway = MultiExchangeBotGateway()
        with patch.object(gateway, "klines", return_value=[{"close": 45000.5}]) as klines:
            result = gateway.ticker("BTCUSDC", exchange="binance")

        klines.assert_called_once_with("BTCUSDC", "1m", limit=1, exchange="binance")
        assert result == {"lastPrice": "45000.5"}

    def test_ticker_returns_empty_dict_when_no_klines_available(self):
        from bots.execution import MultiExchangeBotGateway

        gateway = MultiExchangeBotGateway()
        with patch.object(gateway, "klines", return_value=[]):
            result = gateway.ticker("BTCUSDC")

        assert result == {}


class TestSymbolInfo:
    def test_symbol_info_reports_tradeable_when_market_active(self, monkeypatch):
        from bots.execution import MultiExchangeBotGateway

        fake_market = {"active": True}
        fake_exchange_instance = MagicMock()
        fake_exchange_instance.market.return_value = fake_market
        fake_ccxt = SimpleNamespace(binance=MagicMock(return_value=fake_exchange_instance))
        monkeypatch.setitem(sys.modules, "ccxt", fake_ccxt)

        gateway = MultiExchangeBotGateway()
        result = gateway.symbol_info("BTCUSDC", exchange="binance")

        assert result == {"status": "TRADING", "isSpotTradingAllowed": True}
        fake_exchange_instance.market.assert_called_once_with("BTC/USDC")

    def test_symbol_info_reports_not_tradeable_when_market_inactive(self, monkeypatch):
        from bots.execution import MultiExchangeBotGateway

        fake_exchange_instance = MagicMock()
        fake_exchange_instance.market.return_value = {"active": False}
        fake_ccxt = SimpleNamespace(binance=MagicMock(return_value=fake_exchange_instance))
        monkeypatch.setitem(sys.modules, "ccxt", fake_ccxt)

        gateway = MultiExchangeBotGateway()
        result = gateway.symbol_info("BTCUSDC")

        assert result == {"status": "BREAK", "isSpotTradingAllowed": False}


class TestClientResolution:
    def test_client_raises_400_when_user_has_no_settings_row(self, patch_db_session):
        from bots.execution import MultiExchangeBotGateway

        gateway = MultiExchangeBotGateway()

        with pytest.raises(HTTPException) as exc_info:
            gateway._client("nonexistent-user-id", "binance")

        assert exc_info.value.status_code == 400
        assert "not configured" in exc_info.value.detail

    def test_client_raises_400_when_no_credentials_for_exchange(self, patch_db_session):
        from bots.execution import MultiExchangeBotGateway

        user_id = _create_user()

        with patch("bots.execution.from_user_settings", side_effect=ValueError("missing keys")):
            gateway = MultiExchangeBotGateway()
            with pytest.raises(HTTPException) as exc_info:
                gateway._client(user_id, "kraken")

        assert exc_info.value.status_code == 400
        assert "missing keys" in exc_info.value.detail


class TestOpenOrdersAndBalances:
    def test_open_orders_delegates_to_resolved_client(self):
        from bots.execution import MultiExchangeBotGateway

        fake_client = MagicMock()
        fake_client.get_open_orders.return_value = ["order-1"]

        gateway = MultiExchangeBotGateway()
        with patch.object(gateway, "_client", return_value=fake_client) as get_client:
            result = gateway.open_orders("user-1", "BTCUSDC", exchange="kraken")

        get_client.assert_called_once_with("user-1", "kraken")
        fake_client.get_open_orders.assert_called_once_with("BTCUSDC")
        assert result == ["order-1"]

    def test_balances_converts_dataclasses_to_plain_dicts(self):
        from bots.execution import MultiExchangeBotGateway
        from market.clients.base import Balance

        fake_client = MagicMock()
        fake_client.get_balances.return_value = [
            Balance(asset="BTC", free=Decimal("1.5"), locked=Decimal("0.5")),
            Balance(asset="USDT", free=Decimal("1000"), locked=Decimal("0")),
        ]

        gateway = MultiExchangeBotGateway()
        with patch.object(gateway, "_client", return_value=fake_client):
            result = gateway.balances("user-1", exchange="binance")

        assert result == [
            {"asset": "BTC", "free": "1.5", "locked": "0.5"},
            {"asset": "USDT", "free": "1000", "locked": "0"},
        ]


class TestPlaceOrder:
    def test_place_order_forwards_quote_order_quantity_to_client(self):
        from bots.execution import BotOrderRequest, MultiExchangeBotGateway
        from market.clients.base import OrderResult

        fake_client = MagicMock()
        fake_client.place_order.return_value = OrderResult(
            order_id="10001",
            symbol="BTCUSDC",
            side="BUY",
            order_type="MARKET",
            status="FILLED",
            quantity=Decimal("0.002"),
            price=Decimal("50000"),
        )
        order = BotOrderRequest(
            symbol="BTCUSDC",
            side="BUY",
            order_type="MARKET",
            quote_order_quantity=Decimal("100"),
            client_order_id="bot-abc-123",
        )

        gateway = MultiExchangeBotGateway()
        with patch.object(gateway, "_client", return_value=fake_client) as get_client:
            response = gateway.place_order("user-1", order, exchange="binance")

        get_client.assert_called_once_with("user-1", "binance")
        fake_client.place_order.assert_called_once_with(
            symbol="BTCUSDC",
            side="BUY",
            order_type="MARKET",
            quantity=None,
            price=None,
            quote_quantity=Decimal("100"),
        )
        assert response == {
            "status": "FILLED",
            "orderId": "10001",
            "clientOrderId": "bot-abc-123",
            "executedQty": "0.002",
            "cummulativeQuoteQty": "100.000",
        }

    def test_place_order_reports_zero_quote_quantity_when_no_execution_price(self):
        """Ordre MARKET dont la reponse exchange n'inclut pas de prix moyen execute
        (ex: ordre rejete avant execution) -- la synthese ne doit pas planter, ni
        inventer un montant depense."""
        from bots.execution import BotOrderRequest, MultiExchangeBotGateway
        from market.clients.base import OrderResult

        fake_client = MagicMock()
        fake_client.place_order.return_value = OrderResult(
            order_id="10002",
            symbol="ETHUSDC",
            side="SELL",
            order_type="MARKET",
            status="REJECTED",
            quantity=Decimal("0"),
            price=None,
        )
        order = BotOrderRequest(symbol="ETHUSDC", side="SELL", order_type="MARKET", quantity=Decimal("1"))

        gateway = MultiExchangeBotGateway()
        with patch.object(gateway, "_client", return_value=fake_client):
            response = gateway.place_order("user-1", order)

        assert response["cummulativeQuoteQty"] == "0"
        assert response["status"] == "REJECTED"
