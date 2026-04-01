"""
Base strategy abstract class for the Crypto Trading Bot.
All trading strategies must inherit from this base class.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    This class defines the interface that all strategies must implement
    and provides common functionality for data processing and signal management.
    """

    def __init__(self, name: str, params: dict[str, Any] | None = None):
        """
        Initialize the strategy.

        Args:
            name: Strategy name
            params: Strategy parameters dictionary
        """
        self.name = name
        self.params = params or {}
        self.logger = logging.getLogger(f"strategy.{name}")
        self._last_signal = None
        self._last_processed_time = None

    @abstractmethod
    def compute_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute trading signals from market data.

        Args:
            data: DataFrame with OHLCV data (columns: open, high, low, close, volume, timestamp)

        Returns:
            DataFrame with additional 'signal' column:
            - 1: Buy signal
            - -1: Sell signal
            - 0: Hold/No signal

        Raises:
            ValueError: If data is insufficient or invalid
            NotImplementedError: If not implemented by subclass
        """

    def pre_process(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Pre-process market data before signal computation.
        Override this method to implement custom preprocessing.

        Args:
            data: Raw market data

        Returns:
            Processed market data
        """
        return self._validate_and_clean_data(data)

    def post_process(self, signals: pd.DataFrame) -> pd.DataFrame:
        """
        Post-process signals after computation.
        Override this method to implement custom post-processing.

        Args:
            signals: DataFrame with computed signals

        Returns:
            Post-processed signals
        """
        return self._filter_signals(signals)

    def run(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Complete strategy execution pipeline.

        Args:
            data: Market data DataFrame

        Returns:
            DataFrame with computed signals and indicators
        """
        try:
            self.logger.debug(f"Running strategy {self.name} on {len(data)} data points")

            # Preprocessing
            processed_data = self.pre_process(data)

            # Main signal computation
            signals = self.compute_signals(processed_data)

            # Post-processing
            final_signals = self.post_process(signals)

            # Update last processed time
            if not final_signals.empty:
                self._last_processed_time = (
                    final_signals.index[-1] if hasattr(final_signals, "index") else datetime.now()
                )
                self._last_signal = final_signals["signal"].iloc[-1] if "signal" in final_signals.columns else 0

            self.logger.debug(f"Strategy execution completed, {len(final_signals)} signals generated")
            return final_signals

        except Exception as e:
            self.logger.error(f"Error running strategy {self.name}: {e!s}")
            raise

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get a parameter value with optional default."""
        return self.params.get(key, default)

    def set_parameter(self, key: str, value: Any) -> None:
        """Set a parameter value."""
        self.params[key] = value

    def get_required_indicators(self) -> list[str]:
        """
        Get list of technical indicators required by this strategy.
        Override this method to specify required indicators.

        Returns:
            List of indicator names
        """
        return []

    def validate_parameters(self) -> tuple[bool, str | None]:
        """
        Validate strategy parameters.
        Override this method to implement parameter validation.

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None

    def get_strategy_info(self) -> dict[str, Any]:
        """
        Get strategy information and metadata.

        Returns:
            Dictionary with strategy information
        """
        return {
            "name": self.name,
            "parameters": self.params,
            "required_indicators": self.get_required_indicators(),
            "last_signal": self._last_signal,
            "last_processed_time": self._last_processed_time,
        }

    def _validate_and_clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Validate and clean input data.

        Args:
            data: Input DataFrame

        Returns:
            Cleaned DataFrame

        Raises:
            ValueError: If data is invalid
        """
        if data.empty:
            raise ValueError("Input data cannot be empty")

        required_columns = ["open", "high", "low", "close", "volume"]
        missing_columns = [col for col in required_columns if col not in data.columns]

        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Check for NaN values in critical columns
        critical_columns = ["close", "high", "low"]
        for col in critical_columns:
            if data[col].isna().any():
                self.logger.warning(f"Found NaN values in {col}, forward filling")
                data[col] = data[col].fillna(method="ffill")

        # Ensure proper data types
        numeric_columns = ["open", "high", "low", "close", "volume"]
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")

        # Sort by timestamp if available
        if "timestamp" in data.columns:
            data = data.sort_values("timestamp")

        return data

    def _filter_signals(self, signals: pd.DataFrame) -> pd.DataFrame:
        """
        Filter and clean signals to avoid noise.

        Args:
            signals: DataFrame with signals

        Returns:
            Filtered DataFrame
        """
        if "signal" not in signals.columns:
            return signals

        # Remove consecutive duplicate signals
        signals_copy = signals.copy()
        signals_copy["signal_diff"] = signals_copy["signal"].diff()

        # Keep only signal changes (and first signal)
        mask = (signals_copy["signal_diff"] != 0) | (signals_copy.index == signals_copy.index[0])
        filtered_signals = signals_copy[mask].drop("signal_diff", axis=1)

        # If no signals remain, keep the last signal
        if filtered_signals.empty and not signals.empty:
            filtered_signals = signals.iloc[[-1]].copy()

        return filtered_signals

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', params={self.params})"
