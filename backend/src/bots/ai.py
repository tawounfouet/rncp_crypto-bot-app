"""Deterministic model layer for locked bot templates."""

from __future__ import annotations

from typing import Any


def evaluate_template_model(model_type: str, latest_row: dict[str, Any], strategy_action: str) -> dict[str, Any]:
    """Return a model gate result for the template's configured model type."""
    if model_type == "regime_classifier_v1":
        return _regime_classifier_v1(latest_row, strategy_action)
    if model_type == "trend_classifier_v1":
        return _trend_classifier_v1(latest_row, strategy_action)
    return {
        "model_type": model_type,
        "regime": "unknown",
        "confidence": 0.5,
        "trade_allowed": strategy_action != "HOLD",
        "reason": "No dedicated model registered; strategy signal is passed through.",
    }


def _regime_classifier_v1(latest_row: dict[str, Any], strategy_action: str) -> dict[str, Any]:
    rsi = _float(latest_row.get("rsi"))
    volatility = abs(_float(latest_row.get("price_momentum")))
    if strategy_action == "BUY":
        allowed = rsi <= 45 and volatility <= 0.08
        regime = "mean_reversion_buyable" if allowed else "mean_reversion_blocked"
    elif strategy_action == "SELL":
        allowed = rsi >= 55 and volatility <= 0.08
        regime = "mean_reversion_sellable" if allowed else "mean_reversion_blocked"
    else:
        allowed = False
        regime = "neutral"
    confidence = max(0.1, min(0.95, 1 - abs(rsi - 50) / 100 - min(volatility, 0.2)))
    return {
        "model_type": "regime_classifier_v1",
        "regime": regime,
        "confidence": round(confidence, 4),
        "trade_allowed": allowed,
        "reason": "RSI regime and momentum filter evaluated.",
    }


def _trend_classifier_v1(latest_row: dict[str, Any], strategy_action: str) -> dict[str, Any]:
    spread_pct = _float(latest_row.get("ma_spread_pct"))
    if strategy_action == "BUY":
        allowed = spread_pct > 0
        regime = "uptrend" if allowed else "trend_blocked"
    elif strategy_action == "SELL":
        allowed = spread_pct < 0
        regime = "downtrend" if allowed else "trend_blocked"
    else:
        allowed = False
        regime = "neutral"
    confidence = max(0.1, min(0.95, abs(spread_pct) / 5))
    return {
        "model_type": "trend_classifier_v1",
        "regime": regime,
        "confidence": round(confidence, 4),
        "trade_allowed": allowed,
        "reason": "Moving-average spread trend filter evaluated.",
    }


def _float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
