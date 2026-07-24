"""Tests de l'interface + normaliseur OHLCV partagé (utils/connectors/exchanges/base.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from utils.connectors.exchanges.base import interval_to_timedelta, normalize_ohlcv

# 2025-01-01 12:00:00.000 UTC en millisecondes
OPEN_MS = 1735732800000
# fin d'une bougie 1h : 12:59:59.999
CLOSE_1H = datetime(2025, 1, 1, 12, 59, 59, 999000, tzinfo=UTC)


class TestIntervalToTimedelta:
    def test_minutes(self):
        assert interval_to_timedelta("5m") == timedelta(minutes=5)

    def test_hours(self):
        assert interval_to_timedelta("1h") == timedelta(hours=1)

    def test_days(self):
        assert interval_to_timedelta("1d") == timedelta(days=1)

    def test_weeks(self):
        assert interval_to_timedelta("1w") == timedelta(weeks=1)

    def test_invalid_unit_raises(self):
        with pytest.raises(ValueError):
            interval_to_timedelta("1y")


class TestNormalizeOhlcv:
    def _base(self, **over):
        args = dict(
            symbol="btcusdt",
            interval="1h",
            source="binance",
            open_time_ms=OPEN_MS,
            open=1,
            high=2,
            low=0.5,
            close=1.5,
            volume=10,
        )
        args.update(over)
        return normalize_ohlcv(**args)

    def test_open_time_is_datetime_utc(self):
        assert self._base()["open_time"] == datetime(2025, 1, 1, 12, 0, tzinfo=UTC)

    def test_symbol_uppercased(self):
        assert self._base(symbol="btcusdt")["symbol"] == "BTCUSDT"

    def test_source_is_parameterized(self):
        assert self._base(source="kraken")["source"] == "kraken"

    def test_close_time_used_when_provided(self):
        # cas driver riche (Binance) : close_time fourni
        d = self._base(close_time_ms=OPEN_MS + 3600000 - 1)
        assert d["close_time"] == CLOSE_1H

    def test_close_time_derived_when_absent(self):
        # cas driver maigre (ccxt) : close_time dérivé de l'intervalle
        assert self._base()["close_time"] == CLOSE_1H

    def test_extras_none_when_absent(self):
        d = self._base()
        assert d["quote_asset_volume"] is None
        assert d["number_of_trades"] is None
        assert d["taker_buy_base_volume"] is None
        assert d["taker_buy_quote_volume"] is None

    def test_prices_coerced_to_float(self):
        # les exchanges renvoient souvent des strings
        d = self._base(open="1", high="2", low="0.5", close="1.5", volume="10")
        assert d["close"] == 1.5
        assert isinstance(d["close"], float)
