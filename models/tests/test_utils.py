from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.utils.logger import setup_logger
from src.utils.visualization import plot_confusion_matrix, plot_training_history


class UtilsTests(unittest.TestCase):
    def test_setup_logger_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logger = setup_logger(
                name="test_logger",
                log_dir=tmp,
                log_file="test.log",
                level="INFO",
                file_logging=True,
            )
            logger.info("hello")
            self.assertTrue((Path(tmp) / "test.log").exists())

    def test_visualization_exports_png_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history_path = plot_training_history(
                [
                    {"epoch": 1, "train_loss": 1.0, "validation_loss": 1.1},
                    {"epoch": 2, "train_loss": 0.8, "validation_loss": 0.9},
                ],
                root / "history.png",
            )
            matrix_path = plot_confusion_matrix(
                [0, 1, 2, 1],
                [0, 2, 2, 1],
                ["SELL", "HOLD", "BUY"],
                root / "confusion.png",
            )
            self.assertTrue(history_path.exists())
            self.assertTrue(matrix_path.exists())


if __name__ == "__main__":
    unittest.main()
