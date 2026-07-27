"""Build processed feature datasets."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.config.config_loader import load_config
from src.data.binance import apply_symbol_mapping
from src.data.storage import read_raw_ohlcv_from_minio, write_dataset, write_json
from src.features.indicators import (
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
from src.features.labels import add_signal_labels
from src.utils.logger import get_logger


logger = get_logger(__name__)


def build_features(data: pd.DataFrame, config_path: str = "config.yaml") -> pd.DataFrame:
    """Build features and labels from a validated OHLCV DataFrame."""
    settings = load_config(config_path)
    output = data.copy().sort_values(["symbol", "interval", "open_time"]).reset_index(drop=True)
    indicators = settings.features.technical_indicators
    logger.info("features build start rows=%s columns=%s", len(output), len(output.columns))

    if indicators.returns.get("enabled"):
        output = add_returns(output, indicators.returns["periods"])
        logger.info("features added returns periods=%s columns=%s", indicators.returns["periods"], len(output.columns))
    if indicators.volatility.get("enabled"):
        output = add_volatility(output, indicators.volatility["windows"])
        logger.info(
            "features added volatility windows=%s columns=%s",
            indicators.volatility["windows"],
            len(output.columns),
        )
    if indicators.sma.get("enabled"):
        output = add_sma(output, indicators.sma["windows"])
        logger.info("features added sma windows=%s columns=%s", indicators.sma["windows"], len(output.columns))
    if indicators.ema.get("enabled"):
        output = add_ema(output, indicators.ema["windows"])
        logger.info("features added ema windows=%s columns=%s", indicators.ema["windows"], len(output.columns))
    if indicators.rsi.get("enabled"):
        output = add_rsi(output, indicators.rsi["window"])
        logger.info("features added rsi window=%s columns=%s", indicators.rsi["window"], len(output.columns))
    if indicators.macd.get("enabled"):
        output = add_macd(output, indicators.macd["fast"], indicators.macd["slow"], indicators.macd["signal"])
        logger.info(
            "features added macd fast=%s slow=%s signal=%s columns=%s",
            indicators.macd["fast"],
            indicators.macd["slow"],
            indicators.macd["signal"],
            len(output.columns),
        )
    if indicators.bollinger_bands.get("enabled"):
        output = add_bollinger_bands(
            output, indicators.bollinger_bands["window"], indicators.bollinger_bands["num_std"]
        )
        logger.info(
            "features added bollinger_bands window=%s num_std=%s columns=%s",
            indicators.bollinger_bands["window"],
            indicators.bollinger_bands["num_std"],
            len(output.columns),
        )
    if indicators.volume_sma.get("enabled"):
        output = add_volume_sma(output, indicators.volume_sma["windows"])
        logger.info(
            "features added volume_sma windows=%s columns=%s",
            indicators.volume_sma["windows"],
            len(output.columns),
        )
    if indicators.order_flow.get("enabled"):
        output = add_order_flow_features(output)
        logger.info("features added order_flow columns=%s", len(output.columns))

    if settings.features.missing_values.fill_method == "ffill":
        output = output.ffill()
        logger.info("features missing values filled method=ffill")
    elif settings.features.missing_values.fill_method == "bfill":
        output = output.bfill()
        logger.info("features missing values filled method=bfill")

    output = add_signal_labels(output, settings.labels)
    logger.info("features labels added distribution=%s", output["target"].value_counts().to_dict())
    if settings.features.missing_values.drop_initial_rolling_rows:
        rows_before_dropna = len(output)
        output = output.dropna().reset_index(drop=True)
        logger.info("features dropna complete rows_before=%s rows_after=%s", rows_before_dropna, len(output))
    logger.info("features build complete rows=%s columns=%s", len(output), len(output.columns))
    return output


def build_symbol_features(symbol: str, interval: str, config_path: str = "config.yaml") -> pd.DataFrame:
    """Build and persist features for one symbol/interval.

    Raw OHLCV data is read from MinIO (uploaded by the ingestion job),
    then symbol mapping (invert_price, source_symbol) is applied if configured,
    and finally features are computed and saved locally.
    """
    settings = load_config(config_path)
    symbol = symbol.upper()
    mapping = settings.data.symbol_mappings.get(symbol)
    source_symbol = mapping.source_symbol if mapping else symbol
    logger.info(
        "features job start symbol=%s interval=%s source_symbol=%s",
        symbol,
        interval,
        source_symbol,
    )
    raw = read_raw_ohlcv_from_minio(source_symbol, interval)
    if mapping and mapping.invert_price:
        logger.info("Applying price inversion for symbol=%s (source=%s)", symbol, source_symbol)
        raw = apply_symbol_mapping(raw, symbol, invert_price=True)
    processed = build_features(raw, config_path)
    base_path = Path(settings.data.paths.processed) / symbol.upper() / f"{interval}_features"
    paths = write_dataset(
        processed,
        base_path,
        settings.data.formats.processed_primary,
        settings.data.formats.processed_exports,
        metadata={
            "layer": "processed",
            "dataset": "features",
            "source_layer": "raw",
            "symbol": symbol.upper(),
            "interval": interval,
            "label_report": str(
                Path(settings.data.paths.reports) / "label_distribution" / f"{symbol.upper()}_{interval}.json"
            ),
        },
    )
    distribution = processed["target"].value_counts().to_dict()
    report_path = write_json(
        distribution,
        Path(settings.data.paths.reports) / "label_distribution" / f"{symbol.upper()}_{interval}.json",
    )
    logger.info(
        "features job complete symbol=%s interval=%s rows=%s output_files=%s label_report=%s distribution=%s",
        symbol.upper(),
        interval,
        len(processed),
        [str(path) for path in paths],
        report_path,
        distribution,
    )
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Build processed features for MVP datasets.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--symbols", nargs="*")
    parser.add_argument("--interval")
    args = parser.parse_args()

    settings = load_config(args.config)
    symbols = args.symbols or settings.data.symbols
    interval = args.interval or settings.data.primary_interval
    for symbol in symbols:
        build_symbol_features(symbol, interval, args.config)


if __name__ == "__main__":
    main()
