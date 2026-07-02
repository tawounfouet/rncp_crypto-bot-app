"""Job d'ingestion OHLCV : Binance → MinIO (couche raw/).

Ce script est conçu pour être exécuté par Airflow via PythonOperator
ou directement en ligne de commande.

Il réutilise les fonctions pures de models-training/src/data/binance.py
(collecte + mapping klines) sans dépendre de la config lourde AppSettings
(MLflow, PyTorch, etc.).

Usage CLI :
    python collect_ohlcv.py --symbol BTCUSDT --interval 1h
    python collect_ohlcv.py --symbol ETHUSDT --interval 4h --limit 500

Variables d'environnement requises :
    BINANCE_BASE_URL       (optionnel, défaut: https://api.binance.com)
    MINIO_ENDPOINT         ex: minio:9000
    MINIO_ACCESS_KEY       ex: minioadmin
    MINIO_SECRET_KEY       ex: minioadmin
    MINIO_BUCKET           ex: crypto-bot-data
    MINIO_SECURE           0 ou 1 (défaut: 0)
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import requests
from minio import Minio
from minio.error import S3Error

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("ingest.collect_ohlcv")


# ---------------------------------------------------------------------------
# Configuration (variables d'environnement)
# ---------------------------------------------------------------------------

from pathlib import Path

# Chargement du .env local si disponible (pour exécution hors Docker)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

BINANCE_BASE_URL = os.environ.get("BINANCE_BASE_URL", "https://api.binance.com")
BINANCE_REQUEST_TIMEOUT = int(os.environ.get("BINANCE_REQUEST_TIMEOUT", "20"))

# En local (hors Docker), on fallback sur localhost:9000 si non défini
_default_endpoint = "localhost:9000" if not Path("/.dockerenv").exists() else "minio:9000"

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", _default_endpoint)
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", os.environ.get("MINIO_ROOT_USER", "minioadmin"))
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin"))
MINIO_SECURE = os.environ.get("MINIO_SECURE", "0").lower() in ("true", "1", "yes")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "crypto-bot-data")


# ---------------------------------------------------------------------------
# Collecte Binance (fonctions pures, sans AppSettings)
# ---------------------------------------------------------------------------

#: Colonnes retournées par l'endpoint /api/v3/klines
KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "number_of_trades",
    "taker_buy_base_volume", "taker_buy_quote_volume",
]


def _ms_to_utc(value: int | str) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


def _map_kline(symbol: str, interval: str, raw: list[Any]) -> dict[str, Any]:
    """Convertit une kline brute Binance en dict OHLCV normalisé."""
    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "open_time": _ms_to_utc(raw[0]),
        "open": float(raw[1]),
        "high": float(raw[2]),
        "low": float(raw[3]),
        "close": float(raw[4]),
        "volume": float(raw[5]),
        "close_time": _ms_to_utc(raw[6]),
        "quote_asset_volume": float(raw[7]) if raw[7] not in (None, "") else None,
        "number_of_trades": int(raw[8]) if raw[8] not in (None, "") else None,
        "taker_buy_base_volume": float(raw[9]) if raw[9] not in (None, "") else None,
        "taker_buy_quote_volume": float(raw[10]) if raw[10] not in (None, "") else None,
        "source": "binance",
    }


def fetch_klines(
    symbol: str,
    interval: str,
    limit: int = 1000,
    start_time_ms: int | None = None,
    end_time_ms: int | None = None,
) -> list[dict[str, Any]]:
    """Collecte les klines depuis l'API publique Binance (sans clé API).

    Args:
        symbol: Paire de trading (ex: BTCUSDT)
        interval: Intervalle (ex: 1h, 4h, 1d)
        limit: Nombre de klines (max 1000)
        start_time_ms: Timestamp de début en millisecondes
        end_time_ms: Timestamp de fin en millisecondes

    Returns:
        Liste de dictionnaires OHLCV normalisés
    """
    url = f"{BINANCE_BASE_URL.rstrip('/')}/api/v3/klines"
    params: dict[str, Any] = {
        "symbol": symbol.upper(),
        "interval": interval,
        "limit": limit,
    }
    if start_time_ms is not None:
        params["startTime"] = start_time_ms
    if end_time_ms is not None:
        params["endTime"] = end_time_ms

    logger.info("binance fetch symbol=%s interval=%s limit=%s", symbol.upper(), interval, limit)
    resp = requests.get(url, params=params, timeout=BINANCE_REQUEST_TIMEOUT)
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"Binance request failed symbol={symbol.upper()} interval={interval}: {resp.text}"
        ) from exc

    rows = [_map_kline(symbol, interval, k) for k in resp.json()]
    logger.info("binance fetch complete symbol=%s interval=%s rows=%s", symbol.upper(), interval, len(rows))
    return rows


# ---------------------------------------------------------------------------
# Stockage MinIO
# ---------------------------------------------------------------------------

def _get_minio_client() -> Minio:
    """Crée et retourne un client MinIO configuré depuis les variables d'env."""
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )
    logger.info("minio client ready endpoint=%s", MINIO_ENDPOINT)
    return client


def _ensure_bucket(client: Minio, bucket: str) -> None:
    """Crée le bucket s'il n'existe pas."""
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("minio bucket created bucket=%s", bucket)
    else:
        logger.info("minio bucket exists bucket=%s", bucket)


def upload_dataframe_parquet(
    client: Minio,
    df: pd.DataFrame,
    object_key: str,
    bucket: str = MINIO_BUCKET,
) -> None:
    """Sérialise un DataFrame en Parquet et l'upload dans MinIO.

    Args:
        client: Client MinIO initialisé
        df: DataFrame à persister
        object_key: Chemin de l'objet dans le bucket (ex: raw/BTCUSDT/1h/2026-06-09.parquet)
        bucket: Nom du bucket cible
    """
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    size = buffer.tell()
    buffer.seek(0)

    try:
        client.put_object(
            bucket,
            object_key,
            buffer,
            size,
            content_type="application/vnd.apache.parquet",
        )
        logger.info(
            "minio upload ok bucket=%s key=%s rows=%s size_bytes=%s",
            bucket, object_key, len(df), size,
        )
    except S3Error as exc:
        raise RuntimeError(f"MinIO upload failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Logique principale du job
# ---------------------------------------------------------------------------

def run_ingestion(
    symbol: str,
    interval: str,
    limit: int = 1000,
    bucket: str = MINIO_BUCKET,
) -> str:
    """Collecte les klines Binance et les persiste dans MinIO (format Parquet).

    La clé de l'objet suit la convention :
        raw/ohlcv/<SYMBOL>/<interval>/<YYYY-MM-DD>.parquet

    Args:
        symbol: Paire de trading (ex: BTCUSDT)
        interval: Intervalle de temps (ex: 1h)
        limit: Nombre de klines à collecter (max 1000 par appel)
        bucket: Bucket MinIO cible

    Returns:
        Clé de l'objet créé dans MinIO
    """
    # 1. Collecte
    rows = fetch_klines(symbol=symbol, interval=interval, limit=limit)
    if not rows:
        raise ValueError(f"Aucune donnée collectée pour {symbol} {interval}")

    df = pd.DataFrame(rows)
    logger.info(
        "dataframe ready symbol=%s interval=%s rows=%s columns=%s",
        symbol.upper(), interval, len(df), len(df.columns),
    )

    # 2. Clé MinIO : raw/ohlcv/BTCUSDT/1h/2026-06-09.parquet
    run_date = datetime.now(UTC).strftime("%Y-%m-%d")
    object_key = f"raw/ohlcv/{symbol.upper()}/{interval}/{run_date}.parquet"

    # 3. Upload
    client = _get_minio_client()
    _ensure_bucket(client, bucket)
    upload_dataframe_parquet(client, df, object_key, bucket)

    logger.info(
        "ingestion complete symbol=%s interval=%s object=s3://%s/%s",
        symbol.upper(), interval, bucket, object_key,
    )
    return object_key


# ---------------------------------------------------------------------------
# Point d'entrée CLI (utilisé aussi par Airflow via BashOperator si besoin)
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collecte OHLCV depuis Binance et stocke dans MinIO."
    )
    parser.add_argument("--symbol", required=True, help="Paire de trading ex: BTCUSDT")
    parser.add_argument("--interval", required=True, help="Intervalle ex: 1h, 4h, 1d")
    parser.add_argument("--limit", type=int, default=1000, help="Nombre de klines (max 1000)")
    parser.add_argument("--bucket", default=MINIO_BUCKET, help="Bucket MinIO cible")
    args = parser.parse_args()

    try:
        key = run_ingestion(
            symbol=args.symbol,
            interval=args.interval,
            limit=args.limit,
            bucket=args.bucket,
        )
        print(f"✓ Données ingérées : s3://{args.bucket}/{key}")
    except Exception as exc:  # noqa: BLE001
        logger.error("ingestion failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
