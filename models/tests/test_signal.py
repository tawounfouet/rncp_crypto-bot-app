from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.fixtures import sample_features
from src.config.config_loader import load_config
from src.inference.signal import INFERENCE_MODELS, predict_model_signal, predict_random_forest_signal
from src.models.mlp import save_mlp_artifacts, train_mlp


class SignalInferenceTests(unittest.TestCase):
    def test_inference_models_contract(self) -> None:
        self.assertEqual(INFERENCE_MODELS, ("random_forest", "mlp", "xgboost"))

    def test_unsupported_model_rejected(self) -> None:
        with self.assertRaises(ValueError):
            predict_model_signal("lstm", Path("."), sample_features(), "BTCUSDT", "1h")

    def test_predict_model_signal_generic(self) -> None:
        settings = load_config("config.yaml")
        data = sample_features()
        result = train_mlp(data, settings)
        with tempfile.TemporaryDirectory() as tmp:
            save_mlp_artifacts(result, Path(tmp))
            prediction = predict_model_signal("mlp", Path(tmp), data, symbol="BTCUSDT", interval="1h")
            self.assertEqual(prediction.model_name, "mlp")
            self.assertEqual(prediction.signal_value, {"SELL": -1, "HOLD": 0, "BUY": 1}[prediction.signal])

    def test_predict_random_forest_signal_wrapper(self) -> None:
        settings = load_config("config.yaml")
        data = sample_features()
        result = train_mlp(data, settings)
        with tempfile.TemporaryDirectory() as tmp:
            save_mlp_artifacts(result, Path(tmp))
            prediction = predict_random_forest_signal(Path(tmp), data, symbol="BTCUSDT", interval="1h")
            self.assertEqual(prediction.model_name, "random_forest")


if __name__ == "__main__":
    unittest.main()
