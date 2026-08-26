"""Tests du driver Binance natif (utils/connectors/exchanges/binance_native.py).

Le driver délègue à ``normalize_ohlcv`` mais conserve le payload riche (11 champs)
de l'API Binance. Aucun accès réseau : on teste ``map_kline`` sur un tableau brut factice.
"""

from __future__ import annotations

from datetime import UTC, datetime

import utils.connectors.exchanges.binance_native as bn
import pytest
import requests
from utils.connectors.exchanges.binance_native import BinanceMarketDataDriver, map_kline

# Tableau brut tel que renvoyé par /api/v3/klines (11 champs utiles + extras)
# open_time=12:00:00, close_time=12:59:59.999
RAW = [1735732800000, "1", "2", "0.5", "1.5", "10", 1735736399999, "123.4", 7, "3.1", "4.2"]


class TestMapKline:
    def test_source_is_binance(self):
        assert map_kline("btcusdc", "1h", RAW)["source"] == "binance"

    def test_symbol_uppercased(self):
        assert map_kline("btcusdc", "1h", RAW)["symbol"] == "BTCUSDC"

    def test_uses_provided_close_time(self):
        # Binance fournit close_time -> pas de dérivation
        d = map_kline("BTCUSDC", "1h", RAW)
        assert d["close_time"] == datetime(2025, 1, 1, 12, 59, 59, 999000, tzinfo=UTC)

    def test_preserves_rich_extras(self):
        d = map_kline("BTCUSDC", "1h", RAW)
        assert d["quote_asset_volume"] == 123.4
        assert d["number_of_trades"] == 7
        assert d["taker_buy_base_volume"] == 3.1
        assert d["taker_buy_quote_volume"] == 4.2


class TestBinanceMarketDataDriver:
    def test_source_attribute(self):
        assert BinanceMarketDataDriver().source == "binance"

    def test_satisfies_driver_shape(self):
        # structurellement un MarketDataDriver (a bien fetch_klines)
        assert callable(BinanceMarketDataDriver().fetch_klines)


class FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data

def test_fetch_klines_offline(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return FakeResp([[1735732800000, "1", "2", "0.5", "1.5", "10", 1735736399999, "123", 7, "3", "4"]])

    monkeypatch.setattr(bn.requests, "get", fake_get)  # <-- on remplace requests.get

    rows = bn.fetch_klines("BTCUSDC", "1h", limit=1)
    assert rows[0]["source"] == "binance"
    assert "/api/v3/klines" in captured["url"]  # bonne URL
    assert captured["params"]["symbol"] == "BTCUSDC"  # bons params

def test_fetch_klines_http_error_raises(monkeypatch):
    class BadResp:
        text = "boom"

        def raise_for_status(self):
            raise requests.HTTPError("500")

    monkeypatch.setattr(bn.requests, "get", lambda *a, **k: BadResp())
    with pytest.raises(RuntimeError):
        bn.fetch_klines("BTCUSDC", "1h")

def test_driver_fetch_klines_offline(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return FakeResp([[1735732800000, "1", "2", "0.5", "1.5", "10", 1735736399999, "123", 7, "3", "4"]])

    monkeypatch.setattr(bn.requests, "get", fake_get)
    rows = bn.BinanceMarketDataDriver().fetch_klines("BTCUSDC", "1h", limit=1)
    assert rows[0]["source"] == "binance"
