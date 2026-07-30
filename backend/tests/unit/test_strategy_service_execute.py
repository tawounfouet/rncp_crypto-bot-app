"""Tests unitaires pour StrategyService.execute_strategy (branche ML)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import pandas as pd

from auth.models import User
from strategy.models import Strategy, StrategyDeployment
from strategy.service import StrategyService


def _make_user(session) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=f"{uuid.uuid4()}@test.dev",
        username=f"user_{uuid.uuid4().hex[:8]}",
        hashed_password="fake",  # noqa: S106
    )
    session.add(user)
    session.flush()
    return user


def _make_ml_deployment(session, user: User) -> StrategyDeployment:
    strategy = Strategy(
        id=str(uuid.uuid4()),
        user_id=user.id,
        name="Bot test RF",
        strategy_type="ml_random_forest",
        parameters={},
    )
    session.add(strategy)
    session.flush()

    deployment = StrategyDeployment(
        id=str(uuid.uuid4()),
        strategy_id=strategy.id,
        user_id=user.id,
        exchange="binance",
        symbol="BTCUSDT",
        timeframe="1h",
        amount=100,
        status="active",
        start_time=datetime.now(UTC),
    )
    session.add(deployment)
    session.flush()
    return deployment


@pytest.mark.asyncio
async def test_execute_strategy_ml_random_forest_calls_inference(patch_db_session) -> None:
    user = _make_user(patch_db_session)
    deployment = _make_ml_deployment(patch_db_session, user)

    fake_features_df = pd.DataFrame([{"ema_12": 55.0, "macd_signal": 1.2}])

    fake_predict_result = {
        "signal": "SELL",
        "signal_value": -1,
        "confidence": 0.72,
        "probabilities": {
            "0": 0.72,
            "1": 0.18,
            "2": 0.10
        },
        "latency_ms": 12.34,
    }

    service = StrategyService(market_data_service=MagicMock())

    with (
        patch("strategy.service.build_live_feature_frame", return_value=fake_features_df),
        patch("strategy.service.InferenceService") as mock_inference_cls,
    ):
        mock_inference_cls.return_value.feature_columns = list(fake_features_df.columns)
        mock_inference_cls.return_value.predict.return_value = fake_predict_result

        result = await service.execute_strategy(deployment.id)

    assert result["latest_signal"] == fake_predict_result["signal_value"]
    assert result["signal_info"]["confidence"] == fake_predict_result["confidence"]
    assert result["signal_info"]["probabilities"] == fake_predict_result["probabilities"]
    assert result["data_points"] == len(fake_features_df)
