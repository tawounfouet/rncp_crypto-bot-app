"""
Bollinger Bands Strategy implementation.
"""

from typing import Any

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy
from ..indicators import TechnicalIndicators
from ..registry import register_strategy


@register_strategy(
    "bollinger_bands",
    {
        "description": "Bollinger Bands mean reversion strategy",
        "parameters": {
            "bb_period": {"type": "int", "default": 20, "min": 10, "max": 50},
            "bb_std": {"type": "float", "default": 2.0, "min": 1.0, "max": 3.0},
            "rsi_period": {"type": "int", "default": 14, "min": 5, "max": 30},
            "rsi_oversold": {"type": "float", "default": 30, "min": 10, "max": 40},
            "rsi_overbought": {"type": "float", "default": 70, "min": 60, "max": 90},
            "stop_loss": {"type": "float", "default": 0.025, "min": 0.01, "max": 0.1},
            "take_profit": {"type": "float", "default": 0.05, "min": 0.02, "max": 0.2},
        },
    },
)
class BollingerBandsStrategy(BaseStrategy):
    """
    Bollinger Bands Strategy.

    This strategy combines Bollinger Bands with RSI for improved
    mean reversion signals. It looks for price touches of the bands
    confirmed by RSI overbought/oversold conditions.

    Signals:
    - Buy: Price touches lower band AND RSI < oversold threshold
    - Sell: Price touches upper band AND RSI > overbought threshold
    """

    STRATEGY_NAME = "bollinger_bands"

    def __init__(self, name: str = "bollinger_bands", params: dict[str, Any] | None = None):
        super().__init__(name, params)

        # Default parameters
        self.bb_period = self.get_parameter("bb_period", 20)
        self.bb_std = self.get_parameter("bb_std", 2.0)
        self.rsi_period = self.get_parameter("rsi_period", 14)
        self.rsi_oversold = self.get_parameter("rsi_oversold", 30)
        self.rsi_overbought = self.get_parameter("rsi_overbought", 70)
        self.stop_loss = self.get_parameter("stop_loss", 0.025)
        self.take_profit = self.get_parameter("take_profit", 0.05)

    def compute_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute trading signals based on Bollinger Bands and RSI.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            DataFrame with signals and indicators
        """
        min_periods = max(self.bb_period, self.rsi_period + 1)
        if len(data) < min_periods:
            raise ValueError(f"Insufficient data: {len(data)} < {min_periods}")

        # Make a copy to avoid modifying original data
        df = data.copy()

        # Calculate Bollinger Bands
        bb_upper, bb_middle, bb_lower = TechnicalIndicators.bollinger_bands(df["close"], self.bb_period, self.bb_std)
        df["bb_upper"] = bb_upper
        df["bb_middle"] = bb_middle
        df["bb_lower"] = bb_lower

        # Calculate RSI
        df["rsi"] = TechnicalIndicators.rsi(df["close"], self.rsi_period)

        # Calculate Bollinger Band position (where price is relative to bands)
        df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

        # Calculate band width (volatility measure)
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]

        # Initialize signal column
        df["signal"] = 0

        # Buy signal: Price touches or goes below lower band AND RSI is oversold
        buy_condition = (df["close"] <= df["bb_lower"] * 1.001) & (  # Small tolerance for "touching"
            df["rsi"] < self.rsi_oversold
        )

        # Sell signal: Price touches or goes above upper band AND RSI is overbought
        sell_condition = (df["close"] >= df["bb_upper"] * 0.999) & (  # Small tolerance for "touching"
            df["rsi"] > self.rsi_overbought
        )

        df.loc[buy_condition, "signal"] = 1
        df.loc[sell_condition, "signal"] = -1

        # Add squeeze detection (low volatility periods)
        # Squeeze occurs when bands are very narrow
        bb_width_sma = df["bb_width"].rolling(window=20).mean()
        bb_width_std = df["bb_width"].rolling(window=20).std()

        df["bb_squeeze"] = df["bb_width"] < (bb_width_sma - bb_width_std)

        # Add breakout detection (expansion after squeeze)
        df["bb_expansion"] = (df["bb_width"] > df["bb_width"].shift(1)) & (df["bb_squeeze"].shift(1).fillna(False))

        # Price position relative to bands
        df["bb_zone"] = np.where(
            df["close"] < df["bb_lower"],
            "below_lower",
            np.where(
                df["close"] > df["bb_upper"],
                "above_upper",
                np.where(df["close"] > df["bb_middle"], "upper_half", "lower_half"),
            ),
        )

        # Mean reversion strength (how far from center)
        df["mean_reversion_strength"] = abs(df["close"] - df["bb_middle"]) / (df["bb_upper"] - df["bb_middle"])

        # Add entry/exit levels for risk management
        df["stop_loss_level"] = np.where(
            df["signal"] == 1,
            df["close"] * (1 - self.stop_loss),
            np.where(df["signal"] == -1, df["close"] * (1 + self.stop_loss), np.nan),
        )

        df["take_profit_level"] = np.where(
            df["signal"] == 1,
            df["bb_middle"],  # Target middle band for mean reversion
            np.where(
                df["signal"] == -1,
                df["bb_middle"],  # Target middle band for mean reversion
                np.nan,
            ),
        )

        return df

    def get_required_indicators(self) -> list[str]:
        """Get list of required indicators."""
        return ["bb_upper", "bb_middle", "bb_lower", "rsi", "bb_position", "bb_zone"]

    def validate_parameters(self) -> tuple[bool, str | None]:
        """Validate strategy parameters."""
        try:
            if self.bb_period <= 0:
                return False, "Bollinger Bands period must be positive"

            if self.bb_std <= 0:
                return False, "Bollinger Bands standard deviation must be positive"

            if self.rsi_period <= 0:
                return False, "RSI period must be positive"

            if not (0 < self.rsi_oversold < 50):
                return False, "RSI oversold threshold must be between 0 and 50"

            if not (50 < self.rsi_overbought < 100):
                return False, "RSI overbought threshold must be between 50 and 100"

            if self.rsi_oversold >= self.rsi_overbought:
                return (
                    False,
                    "RSI oversold threshold must be less than overbought threshold",
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
                "description": "Bollinger Bands strategy with RSI confirmation for mean reversion trading",
                "timeframes": ["1h", "4h", "1d"],
                "risk_management": {
                    "stop_loss": self.stop_loss,
                    "take_profit": self.take_profit,
                },
                "bollinger_bands": {
                    "period": self.bb_period,
                    "standard_deviations": self.bb_std,
                },
                "rsi_thresholds": {
                    "oversold": self.rsi_oversold,
                    "overbought": self.rsi_overbought,
                },
            }
        )
        return info
