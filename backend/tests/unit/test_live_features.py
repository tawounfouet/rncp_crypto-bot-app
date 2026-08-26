"""
Tests unitaires pour inference/live_features.py
"""

from unittest.mock import patch


def _fake_candle(index: int, price: float) -> dict:
    """Construit une bougie factice au format retourné par fetch_klines/normalize_ohlcv."""
    return {
        "symbol": "BTCUSDC",
        "interval": "1h",
        "source": "binance",
        "open_time": 10,
        "open": price,
        "high": price + 50,
        "low": price - 50,
        "close": price + 10,
        "volume": 12345.456,
        "quote_asset_volume": 1000.0,
        "number_of_trades": 56,
        "taker_buy_base_volume": 0.5,
        "taker_buy_quote_volume": 500,
    }


def _fake_candles(count: int) -> list[dict]:
    """Génère `count` bougies factices consécutives."""
    return [_fake_candle(i, price=100.0 + i *0.1) for i in range(count)]


class TestBuildLiveFeatureFrame:
    def test_returns_dataframe_without_nan(self):
        from inference.live_features import build_live_feature_frame

        # la fenêtre glissante
        # la plus longue utilisée par les indicateurs est sma_50 -> il faut au moins
        # 50 bougies pour avoir ne serait-ce qu'UNE ligne sans NaN après dropna()
        fake_rows = _fake_candles(count=120)

        with patch("inference.live_features.fetch_klines", return_value=fake_rows):
            df = build_live_feature_frame("BTCUSDC", "1h", bars=len(fake_rows))

        assert not df.empty,  "df is empty"
        assert not df.isna().any().any(),  "df contient des NaN"
        assert "rsi_14" in df.columns,  f"df ne contient pas la colonne rsi_14 parmi {df.columns}"

    def test_returns_empty_dataframe_when_no_data(self):
        from inference.live_features import build_live_feature_frame

        with patch("inference.live_features.fetch_klines", return_value=[]):
            df = build_live_feature_frame("BTCUSDC", "1h")

        assert df.empty
