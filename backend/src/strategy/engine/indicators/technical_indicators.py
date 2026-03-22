"""
Technical indicators for trading strategies.
Common technical analysis indicators used in trading strategies.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """
    Collection of technical analysis indicators.

    This class provides static methods for computing various technical indicators
    commonly used in trading strategies.
    """

    @staticmethod
    def simple_moving_average(data: pd.Series, window: int) -> pd.Series:
        """
        Calculate Simple Moving Average (SMA).

        Args:
            data: Price series
            window: Number of periods

        Returns:
            SMA series
        """
        if len(data) < window:
            logger.warning(f"Insufficient data for SMA calculation: {len(data)} < {window}")

        return data.rolling(window=window).mean()

    @staticmethod
    def exponential_moving_average(data: pd.Series, window: int, alpha: Optional[float] = None) -> pd.Series:
        """
        Calculate Exponential Moving Average (EMA).

        Args:
            data: Price series
            window: Number of periods
            alpha: Smoothing factor (if None, calculated as 2/(window+1))

        Returns:
            EMA series
        """
        if alpha is None:
            alpha = 2.0 / (window + 1)

        return data.ewm(alpha=alpha, adjust=False).mean()

    @staticmethod
    def rsi(data: pd.Series, window: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).

        Args:
            data: Price series
            window: Number of periods (default: 14)

        Returns:
            RSI series (0-100)
        """
        if len(data) < window + 1:
            logger.warning(f"Insufficient data for RSI calculation: {len(data)} < {window + 1}")
            return pd.Series(index=data.index, dtype=float)

        delta = data.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def macd(
        data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Args:
            data: Price series
            fast: Fast EMA period (default: 12)
            slow: Slow EMA period (default: 26)
            signal: Signal line EMA period (default: 9)

        Returns:
            Tuple of (MACD line, Signal line, Histogram)
        """
        if len(data) < slow:
            logger.warning(f"Insufficient data for MACD calculation: {len(data)} < {slow}")
            empty_series = pd.Series(index=data.index, dtype=float)
            return empty_series, empty_series, empty_series

        ema_fast = TechnicalIndicators.exponential_moving_average(data, fast)
        ema_slow = TechnicalIndicators.exponential_moving_average(data, slow)

        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.exponential_moving_average(macd_line, signal)
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def bollinger_bands(
        data: pd.Series, window: int = 20, num_std: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands.

        Args:
            data: Price series
            window: Number of periods (default: 20)
            num_std: Number of standard deviations (default: 2.0)

        Returns:
            Tuple of (Upper band, Middle band/SMA, Lower band)
        """
        if len(data) < window:
            logger.warning(f"Insufficient data for Bollinger Bands calculation: {len(data)} < {window}")
            empty_series = pd.Series(index=data.index, dtype=float)
            return empty_series, empty_series, empty_series

        sma = TechnicalIndicators.simple_moving_average(data, window)
        std = data.rolling(window=window).std()

        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)

        return upper_band, sma, lower_band

    @staticmethod
    def stochastic_oscillator(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_window: int = 14,
        d_window: int = 3,
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate Stochastic Oscillator.

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            k_window: %K period (default: 14)
            d_window: %D period (default: 3)

        Returns:
            Tuple of (%K, %D)
        """
        if len(close) < k_window:
            logger.warning(f"Insufficient data for Stochastic calculation: {len(close)} < {k_window}")
            empty_series = pd.Series(index=close.index, dtype=float)
            return empty_series, empty_series

        lowest_low = low.rolling(window=k_window).min()
        highest_high = high.rolling(window=k_window).max()

        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_window).mean()

        return k_percent, d_percent

    @staticmethod
    def average_true_range(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """
        Calculate Average True Range (ATR).

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            window: Number of periods (default: 14)

        Returns:
            ATR series
        """
        if len(close) < 2:
            logger.warning("Insufficient data for ATR calculation")
            return pd.Series(index=close.index, dtype=float)

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=window).mean()

        return atr

    @staticmethod
    def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """
        Calculate Williams %R.

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            window: Number of periods (default: 14)

        Returns:
            Williams %R series (-100 to 0)
        """
        if len(close) < window:
            logger.warning(f"Insufficient data for Williams %R calculation: {len(close)} < {window}")
            return pd.Series(index=close.index, dtype=float)

        highest_high = high.rolling(window=window).max()
        lowest_low = low.rolling(window=window).min()

        williams_r = -100 * ((highest_high - close) / (highest_high - lowest_low))

        return williams_r

    @staticmethod
    def commodity_channel_index(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int = 20,
        constant: float = 0.015,
    ) -> pd.Series:
        """
        Calculate Commodity Channel Index (CCI).

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            window: Number of periods (default: 20)
            constant: Constant factor (default: 0.015)

        Returns:
            CCI series
        """
        if len(close) < window:
            logger.warning(f"Insufficient data for CCI calculation: {len(close)} < {window}")
            return pd.Series(index=close.index, dtype=float)

        typical_price = (high + low + close) / 3
        sma_tp = typical_price.rolling(window=window).mean()
        mean_deviation = typical_price.rolling(window=window).apply(lambda x: np.mean(np.abs(x - np.mean(x))))

        cci = (typical_price - sma_tp) / (constant * mean_deviation)

        return cci

    @staticmethod
    def money_flow_index(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
        window: int = 14,
    ) -> pd.Series:
        """
        Calculate Money Flow Index (MFI).

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            volume: Volume series
            window: Number of periods (default: 14)

        Returns:
            MFI series (0-100)
        """
        if len(close) < window + 1:
            logger.warning(f"Insufficient data for MFI calculation: {len(close)} < {window + 1}")
            return pd.Series(index=close.index, dtype=float)

        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume

        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)

        positive_mf = positive_flow.rolling(window=window).sum()
        negative_mf = negative_flow.rolling(window=window).sum()

        money_ratio = positive_mf / negative_mf
        mfi = 100 - (100 / (1 + money_ratio))

        return mfi

    @staticmethod
    def on_balance_volume(close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Calculate On-Balance Volume (OBV).

        Args:
            close: Close price series
            volume: Volume series

        Returns:
            OBV series
        """
        if len(close) < 2:
            logger.warning("Insufficient data for OBV calculation")
            return pd.Series(index=close.index, dtype=float)

        direction = np.where(close > close.shift(1), 1, np.where(close < close.shift(1), -1, 0))

        obv = (direction * volume).cumsum()

        return obv

    @staticmethod
    def volume_weighted_average_price(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
        window: Optional[int] = None,
    ) -> pd.Series:
        """
        Calculate Volume Weighted Average Price (VWAP).

        Args:
            high: High price series
            low: Low price series
            close: Close price series
            volume: Volume series
            window: Rolling window (if None, uses cumulative VWAP)

        Returns:
            VWAP series
        """
        typical_price = (high + low + close) / 3
        vwap_numerator = typical_price * volume

        if window is None:
            # Cumulative VWAP
            vwap = vwap_numerator.cumsum() / volume.cumsum()
        else:
            # Rolling VWAP
            vwap = vwap_numerator.rolling(window=window).sum() / volume.rolling(window=window).sum()

        return vwap
