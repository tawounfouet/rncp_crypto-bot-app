"""Job de transformation et chargement (Load) : MinIO (Parquet) → PostgreSQL.

Récupère les fichiers Parquet d'OHLCV stockés dans MinIO par le job
d'ingestion, transforme les colonnes pour correspondre au schéma de la
table ``market_data`` et exécute un upsert idempotent.

Usage CLI :
    python load_ohlcv.py --object-key raw/ohlcv/BTCUSDT/1h/2026-06-10.parquet
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import uuid
from datetime import UTC, datetime

import pandas as pd
from minio.error import S3Error
from sqlalchemy import MetaData, Table
from sqlalchemy.dialects.postgresql import insert

from utils.connectors.minio import MinioClient
from utils.connectors.postgres import create_db_engine
from utils.logging import configure_logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "crypto-bot-data")


# ---------------------------------------------------------------------------
# Récupération MinIO
# ---------------------------------------------------------------------------

def download_parquet_dataframe(object_key: str, bucket: str = MINIO_BUCKET) -> pd.DataFrame:
    """Télécharge un fichier Parquet depuis MinIO et le charge en DataFrame."""
    client = MinioClient()
    logger.info("Téléchargement de s3://%s/%s", bucket, object_key)
    try:
        response = client.client.get_object(bucket, object_key)
        data = response.read()
        df = pd.read_parquet(io.BytesIO(data))
        logger.info("Téléchargement réussi. Lignes chargées: %s", len(df))
        return df
    except S3Error as exc:
        raise RuntimeError(f"Échec du téléchargement depuis MinIO: {exc}") from exc
    finally:
        try:
            response.close()
            response.release_conn()
        except NameError:
            pass


# ---------------------------------------------------------------------------
# Transformation et Chargement
# ---------------------------------------------------------------------------

COLUMN_MAPPING = {
    "open": "open_price",
    "high": "high_price",
    "low": "low_price",
    "close": "close_price",
    "interval": "interval_timeframe",
    "source": "exchange",
}


def transform_and_load(df: pd.DataFrame, db_url: str | None = None) -> None:
    """Transforme les données OHLCV et exécute l'upsert dans PostgreSQL."""
    if df.empty:
        logger.warning("DataFrame vide, aucune donnée à charger.")
        return

    # 1. Renommer les colonnes pour correspondre au schéma Postgres
    df = df.rename(columns=COLUMN_MAPPING)

    # 2. Ajustements et complétions de colonnes
    if "exchange" not in df.columns:
        df["exchange"] = "binance"
    else:
        df["exchange"] = df["exchange"].fillna("binance")

    # Génération d'identifiants déterministes UUIDv5
    def generate_uuid5(row: pd.Series) -> str:
        open_time_str = pd.to_datetime(row["open_time"]).strftime("%Y-%m-%dT%H:%M:%S")
        unique_key = (
            f"cryptobot.{row['symbol'].lower()}.{row['exchange'].lower()}"
            f".{row['interval_timeframe'].lower()}.{open_time_str}"
        )
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_key))

    df["id"] = df.apply(generate_uuid5, axis=1)

    now_utc = datetime.now(UTC).replace(tzinfo=None)
    df["created_at"] = now_utc
    df["updated_at"] = now_utc

    # 3. Connexion et upsert
    engine = create_db_engine(db_url)
    metadata = MetaData()

    try:
        market_data_table = Table("market_data", metadata, autoload_with=engine)
    except Exception as exc:
        logger.error(
            "La table 'market_data' n'existe pas ou n'est pas accessible. "
            "Assurez-vous que le backend a initialisé la base de données : %s", exc
        )
        raise

    records = df.to_dict(orient="records")

    stmt = insert(market_data_table).values(records)

    update_cols = {
        col.name: stmt.excluded[col.name]
        for col in market_data_table.columns
        if col.name not in ["id", "created_at", "symbol", "exchange", "interval_timeframe", "open_time"]
    }
    update_cols["updated_at"] = stmt.excluded.updated_at

    upsert_stmt = stmt.on_conflict_do_update(
        constraint="uq_market_data_symbol_time",
        set_=update_cols,
    )

    with engine.begin() as conn:
        conn.execute(upsert_stmt)

    logger.info("Upsert terminé avec succès pour %s lignes.", len(records))


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def run_loading(object_key: str, bucket: str = MINIO_BUCKET, db_url: str | None = None) -> None:
    """Télécharge le fichier de MinIO et le charge dans PostgreSQL."""
    df = download_parquet_dataframe(object_key, bucket)
    transform_and_load(df, db_url)


def main() -> None:
    configure_logging(name="transform.load_ohlcv", level="INFO")
    parser = argparse.ArgumentParser(
        description="Charge les données OHLCV depuis MinIO dans PostgreSQL."
    )
    parser.add_argument("--object-key", required=True, help="Clé de l'objet Parquet dans MinIO")
    parser.add_argument("--bucket", default=MINIO_BUCKET, help="Bucket MinIO source")
    parser.add_argument("--db-url", default=None, help="URL de connexion à la base de données")
    args = parser.parse_args()

    try:
        run_loading(object_key=args.object_key, bucket=args.bucket, db_url=args.db_url)
        print("✓ Données chargées avec succès dans la base de données.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Échec du chargement : %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
