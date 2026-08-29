from __future__ import annotations

import tempfile
import threading
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

    def test_register_best_model_survives_concurrent_calls(self) -> None:
        """Regression pour la course constatee en conditions reelles le 2026-08-29 :
        ml_pipeline entraine desormais plusieurs paires en parallele pour un meme
        model_name (ex. train_random_forest_BTCUSDC et train_random_forest_ETHUSDC),
        qui ecrivent toutes les deux vers le meme registre local non qualifie par
        paire -- sans serialisation, shutil.rmtree/copytree se marchaient dessus et
        levaient une exception (500 cote ml-api)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            errors: list[Exception] = []

            def _register(symbol: str) -> None:
                artifact_dir = root / "artifacts" / "random_forest" / f"run-{symbol}"
                artifact_dir.mkdir(parents=True)
                (artifact_dir / "model.joblib").write_text(f"fake-{symbol}", encoding="utf-8")
                try:
                    register_best_model(artifact_dir, root / "registry", "random_forest")
                except Exception as exc:  # pragma: no cover - fail via `errors` assertion below
                    errors.append(exc)

            threads = [threading.Thread(target=_register, args=(symbol,)) for symbol in ("BTCUSDC", "ETHUSDC")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            destination = root / "registry" / "random_forest" / "best"
            self.assertTrue((destination / "model.joblib").exists())


if __name__ == "__main__":
    unittest.main()
