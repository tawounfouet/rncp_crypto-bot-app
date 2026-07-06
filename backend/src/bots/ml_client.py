"""Client for bot-specific ML predictions served by the ML API."""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


class BotModelUnavailable(RuntimeError):
    """Raised when the bot ML model cannot be used for a worker decision."""


class BotMlClient:
    """Small HTTP client for the ML API bot model endpoint."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float = 10.0) -> None:
        self.base_url = (base_url or os.getenv("ML_API_URL") or "http://crypto-bot-ml-api:8010").rstrip("/")
        self.timeout_seconds = timeout_seconds

    def predict(
        self,
        *,
        model_name: str,
        features: dict[str, float],
        model_version: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model_name": model_name,
            "features": features,
        }
        if model_version:
            payload["model_version"] = model_version

        try:
            logger.info(
                "Calling ML API bot prediction endpoint: POST %s/bot-models/predict model=%s", self.base_url, model_name
            )
            response = requests.post(
                f"{self.base_url}/bot-models/predict",
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise BotModelUnavailable(f"ML API unavailable: {exc}") from exc

        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except ValueError:
                detail = response.text
            raise BotModelUnavailable(f"ML API rejected prediction: {detail or response.status_code}")

        try:
            prediction = response.json()
        except ValueError as exc:
            raise BotModelUnavailable("ML API returned an invalid JSON prediction response") from exc
        logger.info(
            "ML API bot prediction received model=%s version=%s signal=%s",
            prediction.get("model_name") or model_name,
            prediction.get("model_version") or model_version,
            prediction.get("signal"),
        )
        return prediction
