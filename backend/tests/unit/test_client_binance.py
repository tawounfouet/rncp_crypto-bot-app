"""
Tests unitaires pour utils/client_binance.py
"""

import base64
import os

import pytest
from unittest.mock import MagicMock, patch


class TestClientBinanceInit:
    """Tests pour l'initialisation du client Binance."""

    @patch.dict(
        "os.environ",
        {
            "BINANCE_TESTNET_API_KEY": "test_key",
            "BINANCE_TESTNET_API_SECRET": "test_secret",
        },
    )
    @patch("market.clients.binance.Client")
    def test_init_with_valid_credentials(self, mock_client):
        """Initialisation réussie avec des credentials valides."""
        from market.clients.binance import ClientBinance

        client = ClientBinance()

        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        mock_client.assert_called_once_with("test_key", "test_secret")

    @patch.dict("os.environ", {}, clear=True)
    def test_init_without_credentials_raises(self):
        """Initialisation échoue sans credentials."""
        from market.clients.binance import ClientBinance

        with pytest.raises(ValueError, match="Clés API Binance manquantes"):
            ClientBinance()

    @patch("market.clients.binance.Client")
    def test_init_with_explicit_credentials(self, mock_client):
        """Initialisation réussie avec des credentials fournis explicitement."""
        from market.clients.binance import ClientBinance

        client = ClientBinance(api_key="explicit_key", api_secret="explicit_secret")

        assert client.api_key == "explicit_key"
        assert client.api_secret == "explicit_secret"
        mock_client.assert_called_once_with("explicit_key", "explicit_secret")


class TestClientBinanceFromUserSettings:
    """Tests pour la classmethod from_user_settings."""

    @patch("market.clients.binance.Client")
    def test_from_user_settings_uses_decrypted_credentials(self, mock_client_class):
        """from_user_settings cree un client avec les credentials dechiffres du user."""
        from market.clients.binance import ClientBinance

        mock_settings = MagicMock()
        mock_settings.get_api_key.return_value = "decrypted_key"
        mock_settings.get_api_secret.return_value = "decrypted_secret"

        client = ClientBinance.from_user_settings(mock_settings)

        mock_settings.get_api_key.assert_called_once_with("binance")
        mock_settings.get_api_secret.assert_called_once_with("binance")
        assert client.api_key == "decrypted_key"
        assert client.api_secret == "decrypted_secret"

    def test_from_user_settings_raises_without_credentials(self):
        """from_user_settings leve ValueError si les credentials sont absents."""
        from market.clients.binance import ClientBinance

        mock_settings = MagicMock()
        mock_settings.get_api_key.return_value = None
        mock_settings.get_api_secret.return_value = None

        with pytest.raises(ValueError, match="Clés API Binance manquantes"):
            ClientBinance.from_user_settings(mock_settings)


class TestClientBinanceGetPrice:
    """Tests pour la méthode get_price."""

    @patch.dict(
        "os.environ",
        {
            "BINANCE_TESTNET_API_KEY": "test_key",
            "BINANCE_TESTNET_API_SECRET": "test_secret",
        },
    )
    @patch("market.clients.binance.Client")
    def test_get_price_success(self, mock_client_class):
        """get_price retourne le prix correctement."""
        from market.clients.binance import ClientBinance

        mock_client = MagicMock()
        mock_client.get_symbol_ticker.return_value = {
            "symbol": "BTCUSDC",
            "price": "50000.00",
        }
        mock_client_class.return_value = mock_client

        client = ClientBinance()
        result = client.get_price("BTCUSDC")

        assert result["symbol"] == "BTCUSDC"
        assert result["price"] == "50000.00"
        mock_client.get_symbol_ticker.assert_called_once_with(symbol="BTCUSDC")

    @patch.dict(
        "os.environ",
        {
            "BINANCE_TESTNET_API_KEY": "test_key",
            "BINANCE_TESTNET_API_SECRET": "test_secret",
        },
    )
    @patch("market.clients.binance.Client")
    def test_get_price_api_error_returns_none(self, mock_client_class):
        """get_price retourne None en cas d'erreur API."""
        from market.clients.binance import ClientBinance
        from binance.exceptions import BinanceAPIException

        mock_client = MagicMock()
        mock_client.get_symbol_ticker.side_effect = BinanceAPIException(
            response=MagicMock(status_code=400),
            status_code=400,
            text="Invalid symbol",
        )
        mock_client_class.return_value = mock_client

        client = ClientBinance()
        result = client.get_price("INVALID")

        assert result is None


class TestClientBinanceGetAccountBalances:
    """Tests pour la méthode get_account_balances."""

    @patch.dict(
        "os.environ",
        {
            "BINANCE_TESTNET_API_KEY": "test_key",
            "BINANCE_TESTNET_API_SECRET": "test_secret",
        },
    )
    @patch("market.clients.binance.Client")
    def test_get_account_balances_filters_zero(self, mock_client_class):
        """get_account_balances retourne seulement les soldes > 0."""
        from market.clients.binance import ClientBinance

        mock_client = MagicMock()
        mock_client.get_account.return_value = {
            "balances": [
                {"asset": "BTC", "free": "0.5", "locked": "0.0"},
                {"asset": "USDC", "free": "1000.0", "locked": "0.0"},
                {"asset": "ETH", "free": "0.0", "locked": "0.0"},
            ]
        }
        mock_client_class.return_value = mock_client

        client = ClientBinance()
        result = client.get_account_balances()

        assert result == {"BTC": 0.5, "USDC": 1000.0}
        assert "ETH" not in result  # Solde = 0, exclu


class TestClientBinanceGetHistoricalKlines:
    """Tests pour la méthode get_historical_klines."""

    @patch.dict(
        "os.environ",
        {
            "BINANCE_TESTNET_API_KEY": "test_key",
            "BINANCE_TESTNET_API_SECRET": "test_secret",
        },
    )
    @patch("market.clients.binance.Client")
    def test_get_historical_klines_success(self, mock_client_class):
        """get_historical_klines retourne les données OHLCV."""
        from market.clients.binance import ClientBinance

        mock_klines = [
            [1640000000000, "50000", "51000", "49000", "50500", "100"],
            [1640003600000, "50500", "52000", "50000", "51500", "150"],
        ]
        mock_client = MagicMock()
        mock_client.get_historical_klines.return_value = mock_klines
        mock_client_class.return_value = mock_client

        client = ClientBinance()
        result = client.get_historical_klines("BTCUSDC", "1h", "1 day ago UTC")

        assert result == mock_klines
        assert len(result) == 2
