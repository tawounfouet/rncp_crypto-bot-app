"""Technical indicators implemented with pandas."""

from __future__ import annotations

import pandas as pd


def add_returns(data: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    output = data.copy()
    for period in periods:
        output[f"return_{period}"] = output["close"].pct_change(periods=period)
    return output


def add_volatility(data: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    output = data.copy()
    returns = output["close"].pct_change()
    for window in windows:
        output[f"volatility_{window}"] = returns.rolling(window=window).std()
    return output


def add_sma(data: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    output = data.copy()
    for window in windows:
        output[f"sma_{window}"] = output["close"].rolling(window=window).mean()
    return output


def add_ema(data: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    output = data.copy()
    for window in windows:
        output[f"ema_{window}"] = output["close"].ewm(span=window, adjust=False).mean()
    return output


def add_rsi(data: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    output = data.copy()
    delta = output["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()
    rs = avg_gain / avg_loss
    output[f"rsi_{window}"] = 100 - (100 / (1 + rs))
    return output


def add_macd(data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    output = data.copy()
    ema_fast = output["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = output["close"].ewm(span=slow, adjust=False).mean()
    output["macd"] = ema_fast - ema_slow
    output["macd_signal"] = output["macd"].ewm(span=signal, adjust=False).mean()
    output["macd_hist"] = output["macd"] - output["macd_signal"]
    return output


def add_bollinger_bands(data: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    output = data.copy()
    middle = output["close"].rolling(window=window).mean()
    std = output["close"].rolling(window=window).std()
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    output["bb_upper"] = upper
    output["bb_middle"] = middle
    output["bb_lower"] = lower
    output["bb_width"] = (upper - lower) / middle
    return output


def add_volume_sma(data: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    output = data.copy()
    for window in windows:
        output[f"volume_sma_{window}"] = output["volume"].rolling(window=window).mean()
    return output


def add_order_flow_features(data: pd.DataFrame) -> pd.DataFrame:
    """Compute order flow imbalance features from Binance taker volume columns.

    These features capture buy/sell pressure directly from the order book:
    - buy_pressure_ratio: fraction of quote volume initiated by buyers (0=all sellers, 1=all buyers)
    - volume_delta: net BTC volume bought minus sold by takers
    - trade_size_avg: average USDT size per trade (proxy for institutional vs retail activity)
    """
    output = data.copy()
    quote_vol = output["quote_asset_volume"].replace(0, float("nan"))
    output["buy_pressure_ratio"] = output["taker_buy_quote_volume"] / quote_vol

    taker_sell_base = (output["volume"] - output["taker_buy_base_volume"]).clip(lower=0)
    output["volume_delta"] = output["taker_buy_base_volume"] - taker_sell_base

    n_trades = output["number_of_trades"].replace(0, float("nan"))
    output["trade_size_avg"] = output["quote_asset_volume"] / n_trades

    return output
