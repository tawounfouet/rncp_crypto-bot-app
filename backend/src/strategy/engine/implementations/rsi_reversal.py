"""
RSI Reversal Strategy implementation.
"""

from typing import Any

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy
from ..indicators import TechnicalIndicators
from ..registry import register_strategy


@register_strategy(
    "rsi_reversal",
    {
        "description": "RSI-based mean reversion strategy",
        "parameters": {
            "rsi_period": {"type": "int", "default": 14, "min": 5, "max": 30},
            "oversold_threshold": {
                "type": "float",
                "default": 30,
                "min": 10,
                "max": 40,
            },
            "overbought_threshold": {
                "type": "float",
                "default": 70,
                "min": 60,
                "max": 90,
            },
            "stop_loss": {"type": "float", "default": 0.03, "min": 0.01, "max": 0.1},
            "take_profit": {"type": "float", "default": 0.06, "min": 0.02, "max": 0.2},
        },
    },
)
class RSIReversalStrategy(BaseStrategy):
    """
    RSI Reversal Strategy.

    This strategy uses the Relative Strength Index (RSI) to identify
    overbought and oversold conditions for mean reversion trading.

    Signals:
    - Buy: RSI crosses above oversold threshold (e.g., 30)
    - Sell: RSI crosses below overbought threshold (e.g., 70)
    """

    STRATEGY_NAME = "rsi_reversal"

    def __init__(self, name: str = "rsi_reversal", params: dict[str, Any] | None = None):
        super().__init__(name, params)

        # Default parameters
        self.rsi_period = self.get_parameter("rsi_period", 14)
        self.oversold_threshold = self.get_parameter("oversold_threshold", 30)
        self.overbought_threshold = self.get_parameter("overbought_threshold", 70)
        self.stop_loss = self.get_parameter("stop_loss", 0.03)
        self.take_profit = self.get_parameter("take_profit", 0.06)

        # Validate parameters
        if self.oversold_threshold >= self.overbought_threshold:
            raise ValueError("Oversold threshold must be less than overbought threshold")

    def compute_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute trading signals based on RSI levels.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            DataFrame with signals and RSI indicator
        """
        if len(data) < self.rsi_period + 1:
            raise ValueError(f"Insufficient data: {len(data)} < {self.rsi_period + 1}")

        # Make a copy to avoid modifying original data
        df = data.copy()

        # Calculate RSI
        df["rsi"] = TechnicalIndicators.rsi(df["close"], self.rsi_period)

        # Initialize signal column
        df["signal"] = 0

        # Generate signals based on RSI thresholds
        # Buy signal: RSI crosses above oversold threshold (bullish reversal)
        buy_condition = (df["rsi"] > self.oversold_threshold) & (df["rsi"].shift(1) <= self.oversold_threshold)

        # Sell signal: RSI crosses below overbought threshold (bearish reversal)
        sell_condition = (df["rsi"] < self.overbought_threshold) & (df["rsi"].shift(1) >= self.overbought_threshold)

        df.loc[buy_condition, "signal"] = 1
        df.loc[sell_condition, "signal"] = -1

        # Add RSI zones for analysis
        df["rsi_zone"] = np.where(
            df["rsi"] <= self.oversold_threshold,
            "oversold",
            np.where(df["rsi"] >= self.overbought_threshold, "overbought", "neutral"),
        )

        # Add divergence detection (simple version)
        df["price_momentum"] = df["close"].pct_change(periods=5)
        df["rsi_momentum"] = df["rsi"].diff(periods=5)

        # Bullish divergence: price making lower lows, RSI making higher lows
        bullish_divergence = (df["price_momentum"] < 0) & (df["rsi_momentum"] > 0) & (df["rsi"] < 40)

        # Bearish divergence: price making higher highs, RSI making lower highs
        bearish_divergence = (df["price_momentum"] > 0) & (df["rsi_momentum"] < 0) & (df["rsi"] > 60)

        df["divergence"] = np.where(
            bullish_divergence,
            "bullish",
            np.where(bearish_divergence, "bearish", "none"),
        )

        # Add entry/exit levels for risk management
        df["stop_loss_level"] = np.where(
            df["signal"] == 1,
            df["close"] * (1 - self.stop_loss),
            np.where(df["signal"] == -1, df["close"] * (1 + self.stop_loss), np.nan),
        )

        df["take_profit_level"] = np.where(
            df["signal"] == 1,
            df["close"] * (1 + self.take_profit),
            np.where(df["signal"] == -1, df["close"] * (1 - self.take_profit), np.nan),
        )

        return df

    def get_required_indicators(self) -> list[str]:
        """Get list of required indicators."""
        return ["rsi", "rsi_zone", "divergence"]

    def validate_parameters(self) -> tuple[bool, str | None]:
        """Validate strategy parameters."""
        try:
            if self.rsi_period <= 0:
                return False, "RSI period must be positive"

            if not (0 < self.oversold_threshold < 50):
                return False, "Oversold threshold must be between 0 and 50"

            if not (50 < self.overbought_threshold < 100):
                return False, "Overbought threshold must be between 50 and 100"

            if self.oversold_threshold >= self.overbought_threshold:
                return (
                    False,
                    "Oversold threshold must be less than overbought threshold",
                )

            if not (0 < self.stop_loss < 1):
                return False, "Stop loss must be between 0 and 1"

            if not (0 < self.take_profit < 1):
                return False, "Take profit must be between 0 and 1"

            return True, None

        except Exception as e:
            return False, f"Parameter validation error: {e!s}"

    def get_strategy_info(self) -> dict[str, Any]:
        """Get strategy information."""
        info = super().get_strategy_info()
        info.update(
            {
                "type": "mean_reversion",
                "description": "RSI-based reversal strategy for oversold/overbought conditions",
                "timeframes": ["15m", "1h", "4h"],
                "risk_management": {
                    "stop_loss": self.stop_loss,
                    "take_profit": self.take_profit,
                },
                "thresholds": {
                    "oversold": self.oversold_threshold,
                    "overbought": self.overbought_threshold,
                },
            }
        )
        return info
