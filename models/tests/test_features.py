from __future__ import annotations

import unittest

from src.config.config_loader import load_config
from src.features.build import build_features
from src.features.labels import add_signal_labels
from tests.fixtures import sample_ohlcv


class FeatureTests(unittest.TestCase):
    def test_add_signal_labels(self) -> None:
        settings = load_config("config.yaml")
        data = sample_ohlcv(10)
        labeled = add_signal_labels(data, settings.labels)
        self.assertIn("target", labeled.columns)
        self.assertTrue(set(labeled["target"]).issubset({"BUY", "SELL", "HOLD"}))

    def test_build_features(self) -> None:
        features = build_features(sample_ohlcv(100), "config.yaml")
        expected_columns = {"return_1", "volatility_20", "sma_20", "sma_50", "rsi_14", "macd", "bb_width", "target"}
        self.assertTrue(expected_columns.issubset(set(features.columns)))
        self.assertFalse(features.empty)
        self.assertFalse(features[list(expected_columns - {"target"})].isna().any().any())


if __name__ == "__main__":
    unittest.main()
