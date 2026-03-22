"""
Multi-Indicator Strategy implementation.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Optional

from ..base_strategy import BaseStrategy
from ..indicators import TechnicalIndicators
from ..registry import register_strategy


@register_strategy(
    "multi_indicator",
    {
        "description": "Advanced multi-indicator strategy combining RSI, MACD, and Bollinger Bands",
        "parameters": {
            "rsi_period": {"type": "int", "default": 14, "min": 5, "max": 30},
            "rsi_oversold": {"type": "float", "default": 30, "min": 10, "max": 40},
            "rsi_overbought": {"type": "float", "default": 70, "min": 60, "max": 90},
            "macd_fast": {"type": "int", "default": 12, "min": 5, "max": 20},
            "macd_slow": {"type": "int", "default": 26, "min": 15, "max": 40},
            "macd_signal": {"type": "int", "default": 9, "min": 5, "max": 15},
            "bb_period": {"type": "int", "default": 20, "min": 10, "max": 50},
            "bb_std": {"type": "float", "default": 2.0, "min": 1.0, "max": 3.0},
            "volume_threshold": {
                "type": "float",
                "default": 1.2,
                "min": 1.0,
                "max": 2.0,
            },
            "min_confirmations": {"type": "int", "default": 2, "min": 1, "max": 3},
            "stop_loss": {"type": "float", "default": 0.02, "min": 0.01, "max": 0.1},
            "take_profit": {"type": "float", "default": 0.04, "min": 0.02, "max": 0.2},
        },
    },
)
class MultiIndicatorStrategy(BaseStrategy):
    """
    Multi-Indicator Strategy.

    This advanced strategy combines multiple technical indicators to generate
    high-confidence trading signals. It requires confirmation from multiple
    indicators before generating a signal.

    Indicators used:
    - RSI for overbought/oversold conditions
    - MACD for trend and momentum
    - Bollinger Bands for volatility and mean reversion
    - Volume analysis for confirmation

    Signals are generated only when multiple indicators align.
    """

    STRATEGY_NAME = "multi_indicator"

    def __init__(self, name: str = "multi_indicator", params: Optional[Dict[str, Any]] = None):
        super().__init__(name, params)

        # Default parameters
        self.rsi_period = self.get_parameter("rsi_period", 14)
        self.rsi_oversold = self.get_parameter("rsi_oversold", 30)
        self.rsi_overbought = self.get_parameter("rsi_overbought", 70)

        self.macd_fast = self.get_parameter("macd_fast", 12)
        self.macd_slow = self.get_parameter("macd_slow", 26)
        self.macd_signal = self.get_parameter("macd_signal", 9)

        self.bb_period = self.get_parameter("bb_period", 20)
        self.bb_std = self.get_parameter("bb_std", 2.0)

        self.volume_threshold = self.get_parameter("volume_threshold", 1.2)
        self.min_confirmations = self.get_parameter("min_confirmations", 2)

        self.stop_loss = self.get_parameter("stop_loss", 0.02)
        self.take_profit = self.get_parameter("take_profit", 0.04)

    def compute_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute trading signals based on multiple indicators.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            DataFrame with signals and all indicators
        """
        min_periods = max(self.macd_slow, self.bb_period, self.rsi_period + 1) + self.macd_signal
        if len(data) < min_periods:
            raise ValueError(f"Insufficient data: {len(data)} < {min_periods}")

        # Make a copy to avoid modifying original data
        df = data.copy()

        # Calculate all indicators
        df = self._calculate_indicators(df)

        # Generate individual indicator signals
        df = self._generate_individual_signals(df)

        # Combine signals based on confirmations
        df = self._combine_signals(df)

        # Add risk management levels
        df = self._add_risk_management(df)

        return df

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators."""

        # RSI
        df["rsi"] = TechnicalIndicators.rsi(df["close"], self.rsi_period)

        # MACD
        macd_line, signal_line, histogram = TechnicalIndicators.macd(
            df["close"], self.macd_fast, self.macd_slow, self.macd_signal
        )
        df["macd"] = macd_line
        df["macd_signal"] = signal_line
        df["macd_histogram"] = histogram

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = TechnicalIndicators.bollinger_bands(df["close"], self.bb_period, self.bb_std)
        df["bb_upper"] = bb_upper
        df["bb_middle"] = bb_middle
        df["bb_lower"] = bb_lower
        df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

        # Volume analysis
        df["volume_sma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]

        # Price momentum
        df["price_change"] = df["close"].pct_change()
        df["price_momentum"] = df["close"].pct_change(periods=5)

        return df

    def _generate_individual_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate signals from individual indicators."""

        # RSI signals
        df["rsi_bullish"] = (df["rsi"] > self.rsi_oversold) & (df["rsi"].shift(1) <= self.rsi_oversold)
        df["rsi_bearish"] = (df["rsi"] < self.rsi_overbought) & (df["rsi"].shift(1) >= self.rsi_overbought)

        # MACD signals
        df["macd_bullish"] = (df["macd"] > df["macd_signal"]) & (df["macd"].shift(1) <= df["macd_signal"].shift(1))
        df["macd_bearish"] = (df["macd"] < df["macd_signal"]) & (df["macd"].shift(1) >= df["macd_signal"].shift(1))

        # Additional MACD momentum check
        df["macd_momentum_bullish"] = df["macd_histogram"] > df["macd_histogram"].shift(1)
        df["macd_momentum_bearish"] = df["macd_histogram"] < df["macd_histogram"].shift(1)

        # Bollinger Bands signals
        df["bb_bullish"] = (df["close"] <= df["bb_lower"] * 1.001) & (  # Near or below lower band
            df["rsi"] < 40
        )  # RSI confirmation
        df["bb_bearish"] = (df["close"] >= df["bb_upper"] * 0.999) & (  # Near or above upper band
            df["rsi"] > 60
        )  # RSI confirmation

        # Volume confirmation
        df["volume_confirmation"] = df["volume_ratio"] > self.volume_threshold

        # Trend confirmation (simple)
        df["trend_bullish"] = df["close"] > df["bb_middle"]
        df["trend_bearish"] = df["close"] < df["bb_middle"]

        return df

    def _combine_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Combine individual signals based on confirmation requirements."""

        # Count bullish confirmations
        bullish_signals = [
            "rsi_bullish",
            "macd_bullish",
            "bb_bullish",
            "macd_momentum_bullish",
        ]

        # Count bearish confirmations
        bearish_signals = [
            "rsi_bearish",
            "macd_bearish",
            "bb_bearish",
            "macd_momentum_bearish",
        ]

        # Count confirmations
        df["bullish_count"] = df[bullish_signals].sum(axis=1)
        df["bearish_count"] = df[bearish_signals].sum(axis=1)

        # Initialize signal column
        df["signal"] = 0

        # Generate buy signals
        buy_condition = (
            (df["bullish_count"] >= self.min_confirmations)
            & (df["volume_confirmation"])
            & (df["rsi"] < 80)  # Avoid buying in extreme overbought
        )

        # Generate sell signals
        sell_condition = (
            (df["bearish_count"] >= self.min_confirmations)
            & (df["volume_confirmation"])
            & (df["rsi"] > 20)  # Avoid selling in extreme oversold
        )

        df.loc[buy_condition, "signal"] = 1
        df.loc[sell_condition, "signal"] = -1

        # Signal strength based on number of confirmations
        df["signal_strength"] = np.where(
            df["signal"] == 1,
            df["bullish_count"],
            np.where(df["signal"] == -1, df["bearish_count"], 0),
        )

        return df

    def _add_risk_management(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add risk management levels."""

        # Dynamic stop loss based on ATR
        atr = TechnicalIndicators.average_true_range(df["high"], df["low"], df["close"])
        df["atr"] = atr

        # Stop loss levels
        df["stop_loss_level"] = np.where(
            df["signal"] == 1,
            df["close"] - (df["atr"] * 2),
            np.where(df["signal"] == -1, df["close"] + (df["atr"] * 2), np.nan),
        )

        # Take profit levels
        df["take_profit_level"] = np.where(
            df["signal"] == 1,
            df["close"] + (df["atr"] * 3),
            np.where(df["signal"] == -1, df["close"] - (df["atr"] * 3), np.nan),
        )

        # Alternative fixed percentage levels
        df["stop_loss_fixed"] = np.where(
            df["signal"] == 1,
            df["close"] * (1 - self.stop_loss),
            np.where(df["signal"] == -1, df["close"] * (1 + self.stop_loss), np.nan),
        )

        df["take_profit_fixed"] = np.where(
            df["signal"] == 1,
            df["close"] * (1 + self.take_profit),
            np.where(df["signal"] == -1, df["close"] * (1 - self.take_profit), np.nan),
        )

        return df

    def get_required_indicators(self) -> List[str]:
        """Get list of required indicators."""
        return [
            "rsi",
            "macd",
            "macd_signal",
            "macd_histogram",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "bb_position",
            "volume_ratio",
            "signal_strength",
            "atr",
        ]

    def validate_parameters(self) -> Tuple[bool, Optional[str]]:
        """Validate strategy parameters."""
        try:
            # RSI validation
            if self.rsi_period <= 0:
                return False, "RSI period must be positive"

            if not (0 < self.rsi_oversold < 50):
                return False, "RSI oversold threshold must be between 0 and 50"

            if not (50 < self.rsi_overbought < 100):
                return False, "RSI overbought threshold must be between 50 and 100"

            # MACD validation
            if self.macd_fast >= self.macd_slow:
                return False, "MACD fast period must be less than slow period"

            if self.macd_signal <= 0:
                return False, "MACD signal period must be positive"

            # Bollinger Bands validation
            if self.bb_period <= 0:
                return False, "Bollinger Bands period must be positive"

            if self.bb_std <= 0:
                return False, "Bollinger Bands standard deviation must be positive"

            # Other validations
            if self.volume_threshold < 1.0:
                return False, "Volume threshold must be >= 1.0"

            if not (1 <= self.min_confirmations <= 4):
                return False, "Minimum confirmations must be between 1 and 4"

            if not (0 < self.stop_loss < 1):
                return False, "Stop loss must be between 0 and 1"

            if not (0 < self.take_profit < 1):
                return False, "Take profit must be between 0 and 1"

            return True, None

        except Exception as e:
            return False, f"Parameter validation error: {str(e)}"

    def get_strategy_info(self) -> Dict[str, Any]:
        """Get strategy information."""
        info = super().get_strategy_info()
        info.update(
            {
                "type": "multi_indicator",
                "description": "Advanced strategy combining RSI, MACD, Bollinger Bands with volume confirmation",
                "timeframes": ["1h", "4h", "1d"],
                "complexity": "high",
                "confirmations_required": self.min_confirmations,
                "indicators": {
                    "rsi": {
                        "period": self.rsi_period,
                        "oversold": self.rsi_oversold,
                        "overbought": self.rsi_overbought,
                    },
                    "macd": {
                        "fast": self.macd_fast,
                        "slow": self.macd_slow,
                        "signal": self.macd_signal,
                    },
                    "bollinger_bands": {"period": self.bb_period, "std": self.bb_std},
                    "volume": {"threshold": self.volume_threshold},
                },
                "risk_management": {
                    "stop_loss": self.stop_loss,
                    "take_profit": self.take_profit,
                    "dynamic_levels": True,
                },
            }
        )
        return info
