from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.data.binance import map_kline
from src.data.storage import metadata_path_for, read_dataset, write_dataset
from src.data.validate import validate_ohlcv
from tests.fixtures import sample_ohlcv


class DataTests(unittest.TestCase):
    def test_map_binance_kline(self) -> None:
        kline = [
            1767225600000,
            "100.0",
            "105.0",
            "99.0",
            "101.0",
            "1234.5",
            1767229199999,
            "999.0",
            42,
            "100.0",
            "200.0",
            "0",
        ]
        mapped = map_kline("btcusdt", "1h", kline)
        self.assertEqual(mapped["symbol"], "BTCUSDT")
        self.assertEqual(mapped["interval"], "1h")
        self.assertEqual(mapped["open"], 100.0)
        self.assertEqual(mapped["number_of_trades"], 42)
        self.assertEqual(mapped["source_symbol"], "BTCUSDT")
        self.assertFalse(mapped["price_inverted"])

    def test_map_binance_inverse_pair_kline(self) -> None:
        kline = [
            1767225600000,
            "0.05",
            "0.06",
            "0.04",
            "0.05",
            "100.0",
            1767229199999,
            "5.0",
            42,
            "25.0",
            "1.25",
            "0",
        ]
        mapped = map_kline(
            "btCeth",
            "1h",
            kline,
            source_symbol="ETHBTC",
            invert_price=True,
        )
        self.assertEqual(mapped["symbol"], "BTCETH")
        self.assertEqual(mapped["source_symbol"], "ETHBTC")
        self.assertTrue(mapped["price_inverted"])
        self.assertEqual(mapped["open"], 20.0)
        self.assertEqual(mapped["high"], 25.0)
        self.assertAlmostEqual(mapped["low"], 16.6666666667)
        self.assertEqual(mapped["close"], 20.0)
        self.assertEqual(mapped["volume"], 5.0)

    def test_validate_removes_duplicates(self) -> None:
        data = sample_ohlcv(5)
        duplicated = pd.concat([data, data.iloc[[0]]], ignore_index=True)
        cleaned, report = validate_ohlcv(duplicated, min_valid_candle_ratio=0.5)
        self.assertEqual(len(cleaned), 5)
        self.assertEqual(report.duplicates_removed, 1)

    def test_write_and_read_multiformat_dataset(self) -> None:
        data = sample_ohlcv(5)
        with tempfile.TemporaryDirectory() as tmp:
            base_path = Path(tmp) / "BTCUSDT" / "1h"
            paths = write_dataset(
                data,
                base_path,
                "parquet",
                ["csv", "jsonl"],
                metadata={"layer": "raw", "symbol": "BTCUSDT", "interval": "1h"},
            )
            self.assertEqual({path.suffix for path in paths}, {".parquet", ".csv", ".jsonl"})
            for path in paths:
                loaded = read_dataset(path)
                self.assertEqual(len(loaded), len(data))
                metadata_path = metadata_path_for(path)
                self.assertTrue(metadata_path.exists())
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                self.assertEqual(metadata["row_count"], len(data))
                self.assertEqual(metadata["layer"], "raw")
                self.assertEqual(metadata["symbol"], "BTCUSDT")
                self.assertEqual(metadata["file_name"], path.name)


if __name__ == "__main__":
    unittest.main()
