"""Test the ccxt driver."""

from __future__ import annotations
import os

import pytest

from utils.connectors.exchanges.ccxt_driver import CcxtDriver


class TestToNativeSymbol:
    def test_known_quotes(self):
        assert CcxtDriver.to_native_symbol("BTCUSDC") == "BTC/USDC"
        assert CcxtDriver.to_native_symbol("BTCUSD") == "BTC/USD"
        assert CcxtDriver.to_native_symbol("ETHEUR") == "ETH/EUR"
        assert CcxtDriver.to_native_symbol("ETHUSD") == "ETH/USD"
        assert CcxtDriver.to_native_symbol("LTCEUR") == "LTC/EUR"
        assert CcxtDriver.to_native_symbol("btcusdc") == "BTC/USDC"

    def test_usdt_quote_rejected_mica_compliance(self):
        # USDT n'a pas d'agrement EMT, non conforme MiCA (UE) -- volontairement absent
        # de _KNOWN_QUOTES, cf. commit e2455de. Ne pas re-ajouter USDT ici : si un
        # symbole *USDT apparait a nouveau quelque part (ex. templates de bots), c'est
        # ce symbole qu'il faut corriger vers *USDC, pas cette liste.
        with pytest.raises(ValueError):
            CcxtDriver.to_native_symbol("BTCUSDT")

    def test_unknown_quote_raises(self):
        with pytest.raises(ValueError):
            CcxtDriver.to_native_symbol("ABCXYZ")


class TestCcxtDriver:
    def test_init(self):
        driver = CcxtDriver("binance")
        assert driver.source == "binance"
        assert driver._ccxt_id == "binance"
        assert driver._client is None

        driver = CcxtDriver("kraken")
        assert driver.source == "kraken"
        assert driver._ccxt_id == "kraken"
        assert driver._client is None

    def test_get_client(self):
        driver = CcxtDriver("binance")
        client = driver._get_client()
        assert client is not None
        # The client should be cached
        assert driver._client is client

    def test_fetch_klines_maps_via_fake_client(self):
        class FakeClient:
            def fetch_ohlcv(self, symbol, timeframe, since, limit):
                assert symbol == "BTC/USDC"
                return [[1735732800000, 1, 2, 0.5, 1.5, 10]]
        d = CcxtDriver("binance")
        d._client = FakeClient()                     # injection -> pas de réseau
        out = d.fetch_klines("BTCUSDC", "1h", limit=1)
        assert out[0]["source"] == "binance"
        assert out[0]["symbol"] == "BTCUSDC"
        assert out[0]["quote_asset_volume"] is None

    @pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"), reason="appel réseau réel; set RUN_INTEGRATION=1")
    def test_fetch_klines_real_network(self):
        driver = CcxtDriver("binance")
        # This test will actually hit the Binance API, so we limit the number of klines
        klines = driver.fetch_klines("BTCUSDC", "1h", limit=5)
        assert isinstance(klines, list)
        assert len(klines) <= 5
        for kline in klines:
            assert kline["symbol"] == "BTCUSDC"
            assert kline["interval"] == "1h"
            assert kline["source"] == "binance"

        driver = CcxtDriver("kraken")
        # This test will actually hit the Kraken API, so we limit the number of klines
        klines = driver.fetch_klines("ETHEUR", "1w", limit=5)
        assert isinstance(klines, list)
        assert len(klines) <= 5
        for kline in klines:
            assert kline["symbol"] == "ETHEUR"
            assert kline["interval"] == "1w"
            assert kline["source"] == "kraken"
