"""Job d'ingestion OHLCV multi-exchange → MinIO (couche raw/).

Collecte les klines depuis l'exchange choisi (Binance, Kraken, …) via la couche
driver partagée (``utils.connectors.exchanges``) et les persiste en Parquet dans
MinIO sous la convention :

    raw/ohlcv/{exchange}/{SYMBOL}/{interval}/{YYYY-MM-DD}.parquet

Exécutable par Airflow (PythonOperator) ou en ligne de commande :

    python collect_ohlcv.py --symbol BTCUSDC --interval 1h
    python collect_ohlcv.py --exchange kraken --symbol ETHEUR --interval 1h --limit 500

Variables d'environnement MinIO (voir ``utils.connectors.minio``) :
    MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET, MINIO_SECURE
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from utils.connectors.exchanges import get_market_data_driver
from utils.connectors.minio import MinioClient

# Chargement du .env local si disponible (pour exécution hors Docker)
try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("ingest.collect_ohlcv")


def run_ingestion(
    symbol: str,
    interval: str,
    limit: int = 1000,
    exchange: str = "binance",
    bucket: str | None = None,
) -> str:
    """Collecte les klines de l'exchange et les persiste dans MinIO (Parquet).

    La clé de l'objet suit la convention :
        ``raw/ohlcv/{exchange}/{SYMBOL}/{interval}/{YYYY-MM-DD}.parquet``

    Args:
        symbol: Paire de trading (ex: ``BTCUSDC``, ``ETHEUR``)
        interval: Intervalle de temps (ex: ``1h``)
        limit: Nombre de klines à collecter (max 1000 par appel)
        exchange: Exchange source (ex: ``binance``, ``kraken``) — résolu par le registry
        bucket: Bucket MinIO cible (défaut: ``MINIO_BUCKET`` via MinioClient)

    Returns:
        La clé de l'objet créé dans MinIO.
    """
    # 1. Collecte via le driver de l'exchange (natif Binance, sinon ccxt)
    driver = get_market_data_driver(exchange)
    rows = driver.fetch_klines(symbol, interval, limit=limit)
    if not rows:
        raise ValueError(f"Aucune donnée collectée pour {exchange} {symbol} {interval}")

    df = pd.DataFrame(rows)
    logger.info(
        "dataframe ready exchange=%s symbol=%s interval=%s rows=%s",
        exchange,
        symbol.upper(),
        interval,
        len(df),
    )

    # 2. Clé MinIO scopée par exchange : raw/ohlcv/kraken/ETHEUR/1h/2026-06-09.parquet
    #    (DOIT rester identique au préfixe de lecture models/src/data/storage.py)
    run_date = datetime.now(UTC).strftime("%Y-%m-%d")
    object_key = f"raw/ohlcv/{exchange.lower()}/{symbol.upper()}/{interval}/{run_date}.parquet"

    # 3. Upload (MinioClient garantit l'existence du bucket par défaut)
    client = MinioClient()
    if not client.upload_dataframe(df, object_key, bucket=bucket, fmt="parquet"):
        raise RuntimeError(f"Échec de l'upload MinIO pour {object_key}")

    logger.info("ingestion complete exchange=%s object=%s", exchange, object_key)
    return object_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Collecte OHLCV multi-exchange et stocke dans MinIO.")
    parser.add_argument("--exchange", default="binance", help="Exchange source (ex: binance, kraken)")
    parser.add_argument("--symbol", required=True, help="Paire de trading ex: BTCUSDC")
    parser.add_argument("--interval", required=True, help="Intervalle ex: 1h, 4h, 1d")
    parser.add_argument("--limit", type=int, default=1000, help="Nombre de klines (max 1000)")
    parser.add_argument("--bucket", default=None, help="Bucket MinIO cible (défaut: env MINIO_BUCKET)")
    args = parser.parse_args()

    try:
        key = run_ingestion(
            symbol=args.symbol,
            interval=args.interval,
            limit=args.limit,
            exchange=args.exchange,
            bucket=args.bucket,
        )
        print(f"✓ Données ingérées : {key}")
    except Exception as exc:
        logger.error("ingestion failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
