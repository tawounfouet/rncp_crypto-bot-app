"""
Tests unitaires pour la couche d'execution multi-exchange (issue #13) :
src/market/clients/{base,ccxt_client,binance_native,registry,factory,quotes}.py
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


class TestQuotes:
    """Tests pour src/market/clients/quotes.py."""

    def test_get_default_quote_binance(self):
        from src.market.clients.quotes import get_default_quote

        assert get_default_quote("binance") == "USDT"

    def test_get_default_quote_kraken(self):
        from src.market.clients.quotes import get_default_quote

        assert get_default_quote("kraken") == "EUR"

    def test_get_default_quote_unknown_falls_back_to_usdt(self):
        from src.market.clients.quotes import get_default_quote

        assert get_default_quote("unknown_exchange") == "USDT"

    def test_get_stable_quotes_kraken(self):
        from src.market.clients.quotes import get_stable_quotes

        assert get_stable_quotes("kraken") == ("EUR", "USDC")

    def test_get_stable_quotes_case_insensitive(self):
        from src.market.clients.quotes import get_stable_quotes

        assert get_stable_quotes("KRAKEN") == get_stable_quotes("kraken")


class TestCcxtClient:
    """Tests pour src/market/clients/ccxt_client.py (ccxt mocke, hors ligne)."""

    def _make_client(self, mock_ccxt_module, exchange="kraken", sandbox=False):
        from src.market.clients.ccxt_client import CcxtClient

        with patch.dict("sys.modules", {"ccxt": mock_ccxt_module}):
            return CcxtClient(exchange, api_key="key", api_secret="secret", sandbox=sandbox)

    def _mock_ccxt_module(self, exchange_instance):
        mock_ccxt = MagicMock()
        mock_ccxt.kraken.return_value = exchange_instance
        mock_ccxt.binance.return_value = exchange_instance
        return mock_ccxt

    def test_init_builds_authenticated_client(self):
        exchange_instance = MagicMock()
        mock_ccxt = self._mock_ccxt_module(exchange_instance)

        client = self._make_client(mock_ccxt)

        assert client.source == "kraken"
        mock_ccxt.kraken.assert_called_once_with({"apiKey": "key", "secret": "secret", "enableRateLimit": True})

    def test_sandbox_true_activates_ccxt_sandbox_mode_when_exchange_supports_it(self):
        exchange_instance = MagicMock()
        exchange_instance.urls = {"test": "https://testnet.example", "api": "https://api.example"}

        self._make_client(self._mock_ccxt_module(exchange_instance), exchange="binance", sandbox=True)

        exchange_instance.set_sandbox_mode.assert_called_once_with(True)

    def test_sandbox_true_falls_back_to_validate_only_when_test_url_is_present_but_none(self):
        """Regression : ccxt.kraken().urls contient bien la cle "test" mais avec la valeur
        None (verifie contre le vrai ccxt le 2026-07-27) -- "test" in urls vaut True alors
        qu'il ne faut PAS activer set_sandbox_mode (ca plante cote ccxt sur un clone(None))."""
        exchange_instance = MagicMock()
        exchange_instance.urls = {"api": "https://api.kraken.com", "test": None}

        self._make_client(self._mock_ccxt_module(exchange_instance), exchange="kraken", sandbox=True)

        exchange_instance.set_sandbox_mode.assert_not_called()

    def test_sandbox_true_falls_back_to_validate_only_when_exchange_has_no_testnet(self):
        """Cas Kraken : pas d'URL testnet -> pas de set_sandbox_mode, juste validate=true a l'ordre."""
        exchange_instance = MagicMock()
        exchange_instance.urls = {"api": "https://api.kraken.com"}
        exchange_instance.create_order.return_value = {
            "id": None,  # Kraken en mode validate ne renvoie jamais d'id d'ordre
            "side": "buy",
            "type": "market",
            "status": "closed",
            "amount": "0.1",
        }

        client = self._make_client(self._mock_ccxt_module(exchange_instance), exchange="kraken", sandbox=True)
        client.place_order("BTCEUR", "buy", "market", Decimal("0.1"))

        exchange_instance.set_sandbox_mode.assert_not_called()
        exchange_instance.create_order.assert_called_once_with(
            "BTC/EUR", "market", "buy", 0.1, None, {"validate": True}
        )

    def test_sandbox_false_never_sets_validate_flag(self):
        exchange_instance = MagicMock()
        exchange_instance.urls = {"api": "https://api.kraken.com"}
        exchange_instance.create_order.return_value = {
            "id": "1",
            "side": "buy",
            "type": "market",
            "status": "closed",
            "amount": "0.1",
        }

        client = self._make_client(self._mock_ccxt_module(exchange_instance), exchange="kraken", sandbox=False)
        client.place_order("BTCEUR", "buy", "market", Decimal("0.1"))

        exchange_instance.create_order.assert_called_once_with("BTC/EUR", "market", "buy", 0.1, None, {})

    def test_get_balances_filters_zero_amounts(self):
        exchange_instance = MagicMock()
        exchange_instance.fetch_balance.return_value = {
            "free": {"BTC": 1.5, "EUR": 0},
            "used": {"BTC": 0, "EUR": 100},
        }
        client = self._make_client(self._mock_ccxt_module(exchange_instance))

        balances = {b.asset: b for b in client.get_balances()}

        assert balances["BTC"].free == Decimal("1.5")
        assert balances["BTC"].locked == Decimal("0")
        assert "EUR" in balances  # locked > 0 malgre free == 0
        assert balances["EUR"].locked == Decimal("100")

    def test_get_tickers_filters_by_quote(self):
        exchange_instance = MagicMock()
        exchange_instance.fetch_tickers.return_value = {
            "BTC/EUR": {"last": 60000},
            "BTC/USDC": {"last": 61000},
            "malformed": {"last": 1},
        }
        client = self._make_client(self._mock_ccxt_module(exchange_instance))

        tickers = client.get_tickers(quote="EUR")

        assert len(tickers) == 1
        assert tickers[0].symbol == "BTCEUR"
        assert tickers[0].price == Decimal("60000")

    def test_place_order_normalizes_result(self):
        exchange_instance = MagicMock()
        exchange_instance.create_order.return_value = {
            "id": "123",
            "side": "buy",
            "type": "market",
            "status": "closed",
            "amount": "0.1",
            "price": "60000",
        }
        client = self._make_client(self._mock_ccxt_module(exchange_instance))

        result = client.place_order("BTCEUR", "buy", "market", Decimal("0.1"))

        exchange_instance.create_order.assert_called_once_with("BTC/EUR", "market", "buy", 0.1, None, {})
        assert result.order_id == "123"
        assert result.symbol == "BTCEUR"
        assert result.quantity == Decimal("0.1")
        assert result.price == Decimal("60000")

    def test_cancel_order_normalizes_result(self):
        exchange_instance = MagicMock()
        exchange_instance.cancel_order.return_value = {
            "id": "123",
            "side": "buy",
            "type": "market",
            "status": "canceled",
            "amount": "0.1",
            "price": None,
        }
        client = self._make_client(self._mock_ccxt_module(exchange_instance))

        result = client.cancel_order("BTCEUR", "123")

        exchange_instance.cancel_order.assert_called_once_with("123", "BTC/EUR")
        assert result.status == "canceled"
        assert result.price is None


class TestBinanceNativeClient:
    """Tests pour src/market/clients/binance_native.py (ClientBinance mocke)."""

    @patch("src.market.clients.binance_native.ClientBinance")
    def test_get_balances_filters_zero_amounts(self, mock_binance_cls):
        from src.market.clients.binance_native import BinanceNativeClient

        mock_binance_cls.return_value.get_account_info.return_value = {
            "balances": [
                {"asset": "BTC", "free": "1.0", "locked": "0"},
                {"asset": "ETH", "free": "0", "locked": "0"},
            ]
        }
        client = BinanceNativeClient(api_key="k", api_secret="s")

        balances = client.get_balances()

        assert len(balances) == 1
        assert balances[0].asset == "BTC"
        assert balances[0].free == Decimal("1.0")

    @patch("src.market.clients.binance_native.ClientBinance")
    def test_get_tickers_filters_by_quote(self, mock_binance_cls):
        from src.market.clients.binance_native import BinanceNativeClient

        mock_binance_cls.return_value.get_all_tickers.return_value = [
            {"symbol": "BTCUSDT", "price": "60000"},
            {"symbol": "BTCEUR", "price": "55000"},
        ]
        client = BinanceNativeClient(api_key="k", api_secret="s")

        tickers = client.get_tickers(quote="USDT")

        assert len(tickers) == 1
        assert tickers[0].symbol == "BTCUSDT"
        assert tickers[0].price == Decimal("60000")


class TestRegistry:
    """Tests pour src/market/clients/registry.py."""

    def test_get_exchange_client_defaults_to_ccxt(self):
        from src.market.clients.ccxt_client import CcxtClient
        from src.market.clients.registry import get_exchange_client

        with patch.dict("sys.modules", {"ccxt": MagicMock()}):
            client = get_exchange_client("kraken", "key", "secret")

        assert isinstance(client, CcxtClient)
        assert client.source == "kraken"

    def test_get_exchange_client_uses_native_trapdoor_when_registered(self):
        from src.market.clients import registry

        fake_native = MagicMock()
        registry._NATIVE_CLIENTS["fake_exchange"] = MagicMock(return_value=fake_native)
        try:
            client = registry.get_exchange_client("fake_exchange", "key", "secret")
        finally:
            del registry._NATIVE_CLIENTS["fake_exchange"]

        assert client is fake_native


class TestFactory:
    """Tests pour src/market/clients/factory.py."""

    def test_from_user_settings_raises_without_credentials(self):
        from src.market.clients.factory import from_user_settings

        mock_settings = MagicMock()
        mock_settings.get_api_key.return_value = None
        mock_settings.get_api_secret.return_value = None

        with pytest.raises(ValueError, match="Cles API kraken manquantes"):
            from_user_settings(mock_settings, "kraken")

    def test_from_user_settings_builds_client_with_decrypted_credentials(self):
        from src.market.clients.ccxt_client import CcxtClient
        from src.market.clients.factory import from_user_settings

        mock_settings = MagicMock()
        mock_settings.get_active_mode.return_value = "live"
        mock_settings.get_api_key.return_value = "decrypted_key"
        mock_settings.get_api_secret.return_value = "decrypted_secret"

        with patch.dict("sys.modules", {"ccxt": MagicMock()}):
            client = from_user_settings(mock_settings, "kraken")

        mock_settings.get_api_key.assert_called_once_with("kraken", mode="live")
        mock_settings.get_api_secret.assert_called_once_with("kraken", mode="live")
        assert isinstance(client, CcxtClient)

    def test_from_user_settings_passes_sandbox_flag_when_mode_is_sandbox(self):
        from src.market.clients.factory import from_user_settings

        mock_settings = MagicMock()
        mock_settings.get_active_mode.return_value = "sandbox"
        mock_settings.get_api_key.return_value = "sandbox_key"
        mock_settings.get_api_secret.return_value = "sandbox_secret"

        with patch("src.market.clients.factory.get_exchange_client") as mock_get_client:
            from_user_settings(mock_settings, "binance")

        mock_settings.get_api_key.assert_called_once_with("binance", mode="sandbox")
        mock_get_client.assert_called_once_with(
            "binance", api_key="sandbox_key", api_secret="sandbox_secret", sandbox=True
        )

    def test_from_user_settings_falls_back_to_live_credentials_for_kraken_style_sandbox(self):
        """Kraken n'a pas de cles sandbox : mode actif = sandbox mais les cles live doivent
        etre utilisees (le CcxtClient applique alors validate=true, pas un jeu de cles different)."""
        from src.market.clients.factory import from_user_settings

        mock_settings = MagicMock()
        mock_settings.get_active_mode.return_value = "sandbox"

        def fake_get_api_key(exchange, mode=None):
            return None if mode == "sandbox" else "live_key"

        def fake_get_api_secret(exchange, mode=None):
            return None if mode == "sandbox" else "live_secret"

        mock_settings.get_api_key.side_effect = fake_get_api_key
        mock_settings.get_api_secret.side_effect = fake_get_api_secret

        with patch("src.market.clients.factory.get_exchange_client") as mock_get_client:
            from_user_settings(mock_settings, "kraken")

        mock_get_client.assert_called_once_with(
            "kraken", api_key="live_key", api_secret="live_secret", sandbox=True
        )
