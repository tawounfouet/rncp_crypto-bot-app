from __future__ import annotations

import json
import logging
import tempfile
import time
from pathlib import Path

import joblib
import numpy as np

from utils.connectors.minio import MinioClient
from utils.trading.signals import SIGNAL_TO_VALUE

logger = logging.getLogger(__name__)

MODEL_CACHE_DIR = Path(tempfile.gettempdir()) / "cryptobot_models"
MINIO_MODEL_PREFIX = "models/{model_name}/best"
ARTIFACTS = ["model.joblib", "scaler.joblib", "feature_columns.json"]


class InferenceError(Exception):
    """Raised when model inference fails."""


class InferenceService:
    """Loads a trained model from MinIO and runs predictions.

    Model artifacts are cached locally after the first download.
    """

    def __init__(self, model_name: str = "random_forest", minio_client: MinioClient | None = None):
        self.model_name = model_name
        self._minio = minio_client or MinioClient()
        self._model = None
        self._scaler = None
        self._feature_columns: list[str] | None = None

    @property
    def cache_dir(self) -> Path:
        return MODEL_CACHE_DIR / self.model_name / "best"

    @property
    def model_version(self) -> str:
        return "minio"

    @property
    def feature_columns(self) -> list[str]:
        if self._feature_columns is None:
            self._load()
        return self._feature_columns  # type: ignore

    def _load(self) -> None:
        """Download artifacts from MinIO and load them into memory."""
        cache = self.cache_dir
        bucket = self._minio.default_bucket
        prefix = MINIO_MODEL_PREFIX.format(model_name=self.model_name)

        if not all((cache / f).exists() for f in ARTIFACTS):
            logger.info("Downloading model=%s from s3://%s/%s", self.model_name, bucket, prefix)
            cache.mkdir(parents=True, exist_ok=True)
            for filename in ARTIFACTS:
                obj_key = f"{prefix}/{filename}"
                dest = cache / filename
                ok = self._minio.download_file(obj_key, str(dest), bucket=bucket)
                if not ok:
                    raise InferenceError(
                        f"Failed to download {obj_key} from MinIO. "
                        f"Run `jobs/deploy_model.py --model {self.model_name}` first."
                    )

        logger.info("Loading model=%s from cache=%s", self.model_name, cache)
        self._model = joblib.load(cache / "model.joblib")
        self._scaler = joblib.load(cache / "scaler.joblib")
        self._feature_columns = json.loads((cache / "feature_columns.json").read_text())

    def predict(self, features: dict[str, float]) -> dict:
        """Run inference on a single feature vector.

        Args:
            features: Feature name → value dict. Must include all ``feature_columns``.

        Returns:
            dict with keys: signal, signal_value, confidence, probabilities, latency_ms
        """
        start = time.perf_counter()

        if self._model is None:
            self._load()

        x = np.array([[features[col] for col in self._feature_columns]], dtype=np.float64)
        x_scaled = self._scaler.transform(x)

        proba = self._model.predict_proba(x_scaled)[0]
        classes = list(self._model.classes_)
        probabilities = {str(label): float(p) for label, p in zip(classes, proba, strict=False)}
        signal = max(probabilities, key=probabilities.get)

        latency_ms = (time.perf_counter() - start) * 1000

        return {
            "signal": signal,
            "signal_value": SIGNAL_TO_VALUE.get(signal, 0),
            "confidence": probabilities[signal],
            "probabilities": probabilities,
            "latency_ms": round(latency_ms, 2),
        }
