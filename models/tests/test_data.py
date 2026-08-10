from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.data.binance import apply_symbol_mapping
from src.data.storage import metadata_path_for, read_dataset, write_dataset
from src.data.validate import validate_ohlcv
from tests.fixtures import sample_ohlcv
from utils.connectors.exchanges.binance_native import map_kline


class DataTests(unittest.TestCase):
    def test_map_kline_canonical(self) -> None:
        # map_kline (couche partagee binance_native) : mapping OHLCV canonique
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
        mapped = map_kline("btcusdc", "1h", kline)
        self.assertEqual(mapped["symbol"], "BTCUSDC")
        self.assertEqual(mapped["interval"], "1h")
        self.assertEqual(mapped["open"], 100.0)
        self.assertEqual(mapped["number_of_trades"], 42)
        self.assertEqual(mapped["source"], "binance")

    def test_apply_symbol_mapping_inverts_prices(self) -> None:
        # apply_symbol_mapping : inversion des prix d'une paire inversee (ETHBTC -> BTCETH)
        df = pd.DataFrame(
            [{"symbol": "ETHBTC", "open": 0.05, "high": 0.06, "low": 0.04, "close": 0.05, "volume": 5.0}]
        )
        mapped = apply_symbol_mapping(df, source_symbol="BTCETH", invert_price=True)
        row = mapped.iloc[0]
        self.assertEqual(row["symbol"], "BTCETH")
        self.assertEqual(row["open"], 20.0)  # 1 / 0.05
        self.assertEqual(row["high"], 25.0)  # 1 / 0.04 (high/low permutes apres inversion)
        self.assertAlmostEqual(row["low"], 16.6666666667)  # 1 / 0.06
        self.assertEqual(row["close"], 20.0)
        self.assertEqual(row["volume"], 5.0)  # volume inchange

    def test_apply_symbol_mapping_without_inversion(self) -> None:
        df = pd.DataFrame(
            [{"symbol": "ethusdc", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}]
        )
        mapped = apply_symbol_mapping(df, source_symbol="ethusdc", invert_price=False)
        row = mapped.iloc[0]
        self.assertEqual(row["symbol"], "ETHUSDC")  # source_symbol.upper()
        self.assertEqual(row["open"], 1.0)  # prix inchanges
        self.assertEqual(row["high"], 2.0)
        self.assertEqual(row["low"], 0.5)

    def test_validate_removes_duplicates(self) -> None:
        data = sample_ohlcv(5)
        duplicated = pd.concat([data, data.iloc[[0]]], ignore_index=True)
        cleaned, report = validate_ohlcv(duplicated, min_valid_candle_ratio=0.5)
        self.assertEqual(len(cleaned), 5)
        self.assertEqual(report.duplicates_removed, 1)

    def test_write_and_read_multiformat_dataset(self) -> None:
        data = sample_ohlcv(5)
        with tempfile.TemporaryDirectory() as tmp:
            base_path = Path(tmp) / "BTCUSDC" / "1h"
            paths = write_dataset(
                data,
                base_path,
                "parquet",
                ["csv", "jsonl"],
                metadata={"layer": "raw", "symbol": "BTCUSDC", "interval": "1h"},
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
                self.assertEqual(metadata["symbol"], "BTCUSDC")
                self.assertEqual(metadata["file_name"], path.name)


if __name__ == "__main__":
    unittest.main()
