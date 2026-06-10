from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.mlops.model_card import write_model_card
from src.mlops.registry import register_best_model


class MLOpsTests(unittest.TestCase):
    def test_model_card_and_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "artifacts" / "random_forest" / "run-1"
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "model.joblib").write_text("fake", encoding="utf-8")
            card = write_model_card(artifact_dir, "random_forest", "run-1", {"f1_macro": 0.5})
            self.assertTrue(card.exists())
            registry_path = register_best_model(artifact_dir, root / "registry", "random_forest")
            self.assertTrue((registry_path / "model_card.md").exists())


if __name__ == "__main__":
    unittest.main()
