"""BUY/SELL/HOLD label generation."""

from __future__ import annotations

import pandas as pd

from src.config.settings import LabelSettings


def add_signal_labels(data: pd.DataFrame, settings: LabelSettings) -> pd.DataFrame:
    """Add future-return based labels to a feature DataFrame."""
    output = data.copy()
    future_close = output["close"].shift(-settings.horizon)
    output["future_return"] = future_close / output["close"] - 1

    if settings.threshold_mode == "volatility":
        threshold = (
            output["close"].pct_change().rolling(settings.volatility_window).std() * settings.volatility_multiplier
        )
    else:
        threshold = settings.fixed_threshold

    output["target"] = "HOLD"
    output.loc[output["future_return"] > threshold, "target"] = "BUY"
    output.loc[output["future_return"] < -threshold, "target"] = "SELL"
    output = output.dropna(subset=["future_return", "target"]).reset_index(drop=True)
    return output
