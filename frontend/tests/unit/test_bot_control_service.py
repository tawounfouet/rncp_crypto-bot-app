from __future__ import annotations

from schemas.common import BotRuntimeStatus
from services.bot_control_service import (
    BotControlService,
    ai_labels_from_snapshot,
    normalise_decision_trace,
    select_badge_decision_trace,
)
from utils.constants import ACTION_PAUSE, ACTION_START, ACTION_STOP


def test_list_bots(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = BotControlService(store)
    bots = service.list_bots()
    assert len(bots) >= 2


def test_bot_transitions(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = BotControlService(store)

    bot_id = "bot_sol_trend"
    start_result = service.apply_action(bot_id, ACTION_START)
    assert start_result.success is True
    assert store.bots[bot_id].status == BotRuntimeStatus.RUNNING

    pause_result = service.apply_action(bot_id, ACTION_PAUSE)
    assert pause_result.success is True
    assert store.bots[bot_id].status == BotRuntimeStatus.PAUSED

    stop_result = service.apply_action(bot_id, ACTION_STOP)
    assert stop_result.success is True
    assert store.bots[bot_id].status == BotRuntimeStatus.STOPPED


def test_normalise_ml_api_decision_trace() -> None:
    decision = {
        "id": "decision-123456789",
        "timestamp": "2026-06-28T10:00:00+00:00",
        "strategy_signal": "BUY",
        "risk_decision": "PASS",
        "final_action": "BUY",
        "reason": "Risk gate passed for BUY. Order sent to Binance Spot Testnet.",
        "model_output": {
            "model_source": "ml_api",
            "registry_source": "mlflow",
            "model_name": "bot_rsi_reversal_btcusdt_1h",
            "model_version": "1",
            "confidence": 0.9134,
            "raw_ai_signal": "BUY",
            "deterministic_signal": "HOLD",
            "features": {
                "rsi": 41.123456789,
                "price_change": 0.00123456789,
                "volume": 120.0,
                "sma_short": 65000.0,
                "sma_long": 64800.0,
            },
        },
    }

    trace = normalise_decision_trace(decision)

    assert trace["model_source"] == "ML API"
    assert trace["registry_source"] == "MLflow"
    assert trace["model_name"] == "bot_rsi_reversal_btcusdt_1h"
    assert trace["model_version"] == "v1"
    assert trace["confidence"] == "91.3%"
    assert trace["raw_ai_signal"] == "BUY"
    assert trace["deterministic_signal"] == "HOLD"
    assert trace["order_expected"] is True
    assert trace["features"]["rsi"] == 41.12345679


def test_normalise_legacy_deterministic_decision_trace() -> None:
    decision = {
        "strategy_signal": "HOLD",
        "risk_decision": "PASS",
        "final_action": "HOLD",
        "reason": "No actionable signal on this worker pass.",
        "model_output": {
            "model_type": "regime_classifier_v1",
            "signal_source": "regime_classifier_v1+rsi_reversal",
            "strategy_action": "HOLD",
            "model_result": {"model_type": "regime_classifier_v1"},
        },
    }

    trace = normalise_decision_trace(decision)

    assert trace["model_source"] == "Moteur déterministe"
    assert trace["registry_source"] == "-"
    assert trace["model_name"] == "regime_classifier_v1"
    assert trace["model_version"] == "-"
    assert trace["raw_ai_signal"] == "-"
    assert trace["deterministic_signal"] == "HOLD"
    assert trace["order_expected"] is False


def test_normalise_decision_trace_with_missing_fields_does_not_crash() -> None:
    trace = normalise_decision_trace({"final_action": "HOLD"})

    assert trace["model_source"] == "Moteur déterministe"
    assert trace["model_name"] == "-"
    assert trace["confidence"] == "-"
    assert trace["features"] == {}


def test_ai_labels_from_mlflow_snapshot() -> None:
    labels = ai_labels_from_snapshot(
        {
            "model_type": "mlflow_bot_rsi_reversal_v1",
            "execution_params": {
                "mlflow_model_name": "bot_rsi_reversal_btcusdt_1h",
                "mlflow_model_version": "1",
            },
        }
    )

    assert labels["model_source_label"] == "ML API"
    assert labels["registry_source_label"] == "MLflow"
    assert labels["model_name"] == "bot_rsi_reversal_btcusdt_1h"
    assert labels["model_version"] == "v1"


def test_badge_trace_ignores_error_and_prefers_ml_api() -> None:
    error_trace = normalise_decision_trace(
        {
            "strategy_signal": "ERROR",
            "risk_decision": "ERROR",
            "final_action": "ERROR",
            "model_output": {"error": "temporary worker error"},
        }
    )
    deterministic_trace = normalise_decision_trace(
        {
            "strategy_signal": "HOLD",
            "risk_decision": "PASS",
            "final_action": "HOLD",
            "model_output": {"model_type": "regime_classifier_v1", "strategy_action": "HOLD"},
        }
    )
    ml_trace = normalise_decision_trace(
        {
            "strategy_signal": "BUY",
            "risk_decision": "PASS",
            "final_action": "BUY",
            "model_output": {
                "model_source": "ml_api",
                "registry_source": "mlflow",
                "model_name": "bot_rsi_reversal_btcusdt_1h",
                "model_version": "1",
                "raw_ai_signal": "BUY",
                "confidence": 0.8,
            },
        }
    )

    selected = select_badge_decision_trace([error_trace, deterministic_trace, ml_trace])

    assert selected is ml_trace
    assert selected["model_source"] == "ML API"
    assert selected["signal"] == "BUY"


def test_badge_trace_returns_none_when_only_errors_exist() -> None:
    error_trace = normalise_decision_trace(
        {
            "strategy_signal": "ERROR",
            "risk_decision": "ERROR",
            "final_action": "ERROR",
            "model_output": {"error": "temporary worker error"},
        }
    )

    assert select_badge_decision_trace([error_trace]) is None
