from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.fixtures import sample_features
from src.config.config_loader import load_config
from src.inference.signal import predict_mlp_signal
from src.models.mlp import save_mlp_artifacts, train_mlp


ARTIFACTS = (
    "model.joblib",
    "scaler.joblib",
    "feature_columns.json",
    "metrics.json",
    "confusion_matrix.png",
    "feature_importance.json",
    "feature_importance.png",
)


class MLPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = load_config("config.yaml")

    def test_train_mlp_returns_metrics_and_saves_artifacts(self) -> None:
        data = sample_features()
        result = train_mlp(data, self.settings)
        self.assertIn("f1_macro", result["metrics"])
        self.assertTrue(result["feature_columns"])
        with tempfile.TemporaryDirectory() as tmp:
            save_mlp_artifacts(result, Path(tmp))
            for filename in ARTIFACTS:
                self.assertTrue((Path(tmp) / filename).exists(), f"missing {filename}")

    def test_saved_mlp_predicts_signal(self) -> None:
        data = sample_features()
        result = train_mlp(data, self.settings)
        with tempfile.TemporaryDirectory() as tmp:
            save_mlp_artifacts(result, Path(tmp))
            prediction = predict_mlp_signal(Path(tmp), data, symbol="BTCUSDC", interval="1h")
            self.assertEqual(prediction.model_name, "mlp")
            self.assertIn(prediction.signal, {"SELL", "HOLD", "BUY"})
            self.assertGreaterEqual(prediction.confidence, 0.0)
            self.assertLessEqual(prediction.confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
