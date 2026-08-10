from __future__ import annotations

import unittest

from src.config.config_loader import load_config


class ConfigTests(unittest.TestCase):
    def test_loads_mvp_config(self) -> None:
        settings = load_config("config.yaml")
        self.assertEqual(settings.data.symbols, ["BTCUSDC", "BTCETH"])
        self.assertEqual(settings.data.symbol_mappings["BTCETH"].source_symbol, "ETHBTC")
        self.assertTrue(settings.data.symbol_mappings["BTCETH"].invert_price)
        self.assertEqual(settings.data.primary_interval, "1h")
        self.assertTrue(settings.mlops.enabled)
        self.assertEqual(settings.mlops.tracking_backend, "mlflow")

    def test_split_ratios_sum_to_one(self) -> None:
        settings = load_config("config.yaml")
        total = settings.split.train_ratio + settings.split.validation_ratio + settings.split.test_ratio
        self.assertAlmostEqual(total, 1.0)

    def test_label_mapping(self) -> None:
        settings = load_config("config.yaml")
        self.assertEqual(settings.label_to_id, {"SELL": 0, "HOLD": 1, "BUY": 2})
        self.assertEqual(settings.id_to_label, {0: "SELL", 1: "HOLD", 2: "BUY"})


if __name__ == "__main__":
    unittest.main()
