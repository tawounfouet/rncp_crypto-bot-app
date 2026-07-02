"""Storage utilities for reading/writing datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import logging

import pandas as pd

from utils.connectors.minio import MinioClient

logger = logging.getLogger(__name__)


def metadata_path_for(path: str | Path) -> Path:
    """Get the path for the metadata JSON file corresponding to a dataset.

    Le nom du format est conservé (``1h.csv`` -> ``1h.csv.json``) pour que chaque
    format ait ses propres métadonnées. Sinon tous les formats écraseraient un
    unique ``1h.json`` (ordre d'écriture non déterministe -> test flaky).
    """
    return Path(f"{path}.json")


def read_dataset(path: str | Path) -> pd.DataFrame:
    """Read a dataset from the specified path based on its extension."""
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Dataset not found: {path_obj}")

    if path_obj.suffix == ".parquet":
        return pd.read_parquet(path_obj)
    if path_obj.suffix == ".csv":
        return pd.read_csv(path_obj)
    if path_obj.suffix == ".jsonl":
        return pd.read_json(path_obj, orient="records", lines=True)

    raise ValueError(f"Unsupported dataset format: {path_obj.suffix}")


def read_raw_ohlcv_from_minio(
    symbol: str,
    interval: str,
    exchange: str = "binance",
    bucket: str | None = None,
    minio_client: MinioClient | None = None,
) -> pd.DataFrame:
    """Read all available OHLCV Parquet files from MinIO for a symbol/interval.

    The files follow the convention set by ``jobs/ingest/collect_ohlcv.py``:
        ``raw/ohlcv/{SYMBOL}/{interval}/{YYYY-MM-DD}.parquet``

    Args:
        exchange: Exchange name (e.g. ``binance``, ``kraken``)
        symbol: Trading pair (e.g. ``BTCUSDT``)
        interval: Kline interval (e.g. ``1h``, ``4h``)
        bucket: MinIO bucket (defaults to env ``MINIO_BUCKET`` or ``crypto-bot-data``)
        minio_client: Reusable client instance (created on demand if ``None``)

    Returns:
        Concatenated DataFrame with all available dates, sorted by ``open_time``.
    """
    client = minio_client or MinioClient()
    bucket = bucket or client.default_bucket
    prefix = f"raw/ohlcv/{exchange.lower()}/{symbol.upper()}/{interval}/"

    objects = client.list_objects(prefix=prefix, bucket=bucket)
    if not objects:
        logger.warning("No raw data found in MinIO for prefix=%s bucket=%s", prefix, bucket)
        return pd.DataFrame()

    frames = []
    for obj in objects:
        key = obj["Key"]
        df = client.download_dataframe(key, bucket=bucket, fmt="parquet")
        if df is not None and not df.empty:
            frames.append(df)

    if not frames:
        logger.warning("All Parquet downloads failed prefix=%s bucket=%s", prefix, bucket)
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values("open_time").reset_index(drop=True)
    logger.info(
        "Read %d rows from MinIO prefix=%s bucket=%s (%d files)",
        len(result),
        prefix,
        bucket,
        len(frames),
    )
    return result


def write_dataset(
    data: pd.DataFrame,
    base_path: str | Path,
    primary_format: str,
    export_formats: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[Path]:
    """Write a dataset to multiple formats and generate metadata files."""
    base_obj = Path(base_path)
    base_obj.parent.mkdir(parents=True, exist_ok=True)

    formats = {primary_format}
    if export_formats:
        formats.update(export_formats)

    paths = []
    for fmt in formats:
        file_path = base_obj.with_suffix(f".{fmt}")

        if fmt == "parquet":
            data.to_parquet(file_path, index=False)
        elif fmt == "csv":
            data.to_csv(file_path, index=False)
        elif fmt == "jsonl":
            data.to_json(file_path, orient="records", lines=True)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

        paths.append(file_path)

        if metadata is not None:
            meta = metadata.copy()
            meta["row_count"] = len(data)
            meta["file_name"] = file_path.name
            write_json(meta, metadata_path_for(file_path))

    return paths


def write_json(data: dict[str, Any], path: str | Path) -> Path:
    """Write a dictionary to a JSON file."""
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    path_obj.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path_obj
