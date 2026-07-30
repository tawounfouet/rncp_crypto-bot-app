import logging

import pandas as pd

from utils.connectors.exchanges.binance_native import fetch_klines
from utils.features.indicators import (
    add_bollinger_bands,
    add_ema,
    add_macd,
    add_order_flow_features,
    add_returns,
    add_rsi,
    add_sma,
    add_volatility,
    add_volume_sma,
)

logger = logging.getLogger(__name__)


def build_live_feature_frame(symbol: str, interval: str, bars: int = 200) -> pd.DataFrame:
    rows = fetch_klines(symbol, interval, limit=bars)

    if not rows:
        logger.warning(f"No data received from Binance for {symbol}")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = add_returns(df, [1, 3, 6])
    df = add_volatility(df, [20])
    df = add_sma(df, [20, 50])
    df = add_ema(df, [12, 26])
    df = add_rsi(df, 14)
    df = add_macd(df, 12, 26, 9)
    df = add_bollinger_bands(df, 20, 2.0)
    df = add_volume_sma(df, [20])
    df = add_order_flow_features(df)

    df = df.dropna()
    return df


if __name__ == "__main__":
    df = build_live_feature_frame("BTCUSDT", "1h", 1)
    print("toto")
    print(df)
