"""
Moving Average Crossover Strategy implementation.
"""

from typing import Any

import numpy as np
import pandas as pd

from ..base_strategy import BaseStrategy
from ..indicators import TechnicalIndicators
from ..registry import register_strategy


@register_strategy(
    "moving_average_crossover",
    {
        "description": "Simple moving average crossover strategy",
        "parameters": {
            "fast_period": {"type": "int", "default": 10, "min": 5, "max": 50},
            "slow_period": {"type": "int", "default": 20, "min": 10, "max": 200},
            "stop_loss": {"type": "float", "default": 0.02, "min": 0.01, "max": 0.1},
            "take_profit": {"type": "float", "default": 0.05, "min": 0.02, "max": 0.2},
        },
    },
)
class MovingAverageCrossoverStrategy(BaseStrategy):
    """
    Moving Average Crossover Strategy.

    This strategy generates buy signals when a fast moving average crosses above
    a slow moving average, and sell signals when the fast MA crosses below the slow MA.

    Signals:
    - Buy: Fast MA crosses above Slow MA
    - Sell: Fast MA crosses below Slow MA
    """

    STRATEGY_NAME = "moving_average_crossover"

    def __init__(
        self,
        name: str = "moving_average_crossover",
        params: dict[str, Any] | None = None,
    ):
        super().__init__(name, params)

        # Default parameters
        self.fast_period = self.get_parameter("fast_period", 10)
        self.slow_period = self.get_parameter("slow_period", 20)
        self.stop_loss = self.get_parameter("stop_loss", 0.02)
        self.take_profit = self.get_parameter("take_profit", 0.05)

        # Validate parameters
        if self.fast_period >= self.slow_period:
            raise ValueError("Fast period must be less than slow period")

    def compute_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute trading signals based on moving average crossover.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            DataFrame with signals and moving averages
        """
        if len(data) < self.slow_period:
            raise ValueError(f"Insufficient data: {len(data)} < {self.slow_period}")

        # Make a copy to avoid modifying original data
        df = data.copy()

        # Calculate moving averages
        df["fast_ma"] = TechnicalIndicators.simple_moving_average(df["close"], self.fast_period)
        df["slow_ma"] = TechnicalIndicators.simple_moving_average(df["close"], self.slow_period)

        # Initialize signal column
        df["signal"] = 0

        # Generate crossover signals
        # Buy signal: Fast MA crosses above Slow MA
        bullish_crossover = (df["fast_ma"] > df["slow_ma"]) & (df["fast_ma"].shift(1) <= df["slow_ma"].shift(1))

        # Sell signal: Fast MA crosses below Slow MA
        bearish_crossover = (df["fast_ma"] < df["slow_ma"]) & (df["fast_ma"].shift(1) >= df["slow_ma"].shift(1))

        df.loc[bullish_crossover, "signal"] = 1
        df.loc[bearish_crossover, "signal"] = -1

        # Add additional metrics
        df["ma_spread"] = df["fast_ma"] - df["slow_ma"]
        df["ma_spread_pct"] = (df["ma_spread"] / df["slow_ma"]) * 100

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
        return ["fast_ma", "slow_ma", "ma_spread"]

    def validate_parameters(self) -> tuple[bool, str | None]:
        """Validate strategy parameters."""
        try:
            if self.fast_period <= 0:
                return False, "Fast period must be positive"

            if self.slow_period <= 0:
                return False, "Slow period must be positive"

            if self.fast_period >= self.slow_period:
                return False, "Fast period must be less than slow period"

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
                "type": "trend_following",
                "description": "Moving average crossover strategy for trend identification",
                "timeframes": ["1h", "4h", "1d"],
                "risk_management": {
                    "stop_loss": self.stop_loss,
                    "take_profit": self.take_profit,
                },
            }
        )
        return info
