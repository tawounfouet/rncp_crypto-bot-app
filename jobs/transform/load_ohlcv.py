"""Job de transformation et chargement (Load) : MinIO (Parquet) → PostgreSQL.

Ce script récupère les fichiers Parquet d'OHLCV stockés dans MinIO par le job d'ingestion,
les transforme pour correspondre au schéma PostgreSQL de la table 'market_data'
et les y insère de manière idempotente (upsert).

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
from minio import Minio
from minio.error import S3Error
from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy.dialects.postgresql import insert

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("transform.load_ohlcv")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "0").lower() in ("true", "1", "yes")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "crypto-bot-data")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PWD = os.environ.get("POSTGRES_PWD", "postgres")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "crypto_bot_db")

# Fallback pour local dev sans docker si DATABASE_URL est défini
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PWD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)


# ---------------------------------------------------------------------------
# Récupération MinIO
# ---------------------------------------------------------------------------

def _get_minio_client() -> Minio:
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )


def download_parquet_dataframe(object_key: str, bucket: str = MINIO_BUCKET) -> pd.DataFrame:
    """Télécharge un fichier Parquet depuis MinIO et le charge en DataFrame."""
    client = _get_minio_client()
    logger.info("Téléchargement de s3://%s/%s", bucket, object_key)
    try:
        response = client.get_object(bucket, object_key)
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

def transform_and_load(df: pd.DataFrame, db_url: str = DATABASE_URL) -> None:
    """Transforme les données OHLCV et exécute l'upsert dans PostgreSQL."""
    if df.empty:
        logger.warning("DataFrame vide, aucune donnée à charger.")
        return

    # 1. Renommer les colonnes pour correspondre au schéma Postgres
    rename_mapping = {
        "open": "open_price",
        "high": "high_price",
        "low": "low_price",
        "close": "close_price",
        "interval": "interval_timeframe",
        "source": "exchange",
    }
    df = df.rename(columns=rename_mapping)

    # 2. Ajustements et complétions de colonnes
    if "exchange" not in df.columns:
        df["exchange"] = "binance"
    else:
        df["exchange"] = df["exchange"].fillna("binance")

    # Génération d'identifiants déterministes UUIDv5 pour éviter les doublons et garantir l'idempotence
    # UUIDv5 utilise un namespace UUID (ici standard NAMESPACE_DNS) combiné à une clé unique.
    def generate_uuid5(row: pd.Series) -> str:
        open_time_str = pd.to_datetime(row["open_time"]).strftime("%Y-%m-%dT%H:%M:%S")
        unique_key = f"cryptobot.{row['symbol'].lower()}.{row['exchange'].lower()}.{row['interval_timeframe'].lower()}.{open_time_str}"
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_key))

    df["id"] = df.apply(generate_uuid5, axis=1)

    # Ajout des dates de création/mise à jour
    now_utc = datetime.now(UTC).replace(tzinfo=None) # PostgreSQL timestamp sans fuseau horaire
    df["created_at"] = now_utc
    df["updated_at"] = now_utc

    # 3. Connexion à la base de données
    engine = create_engine(db_url)
    metadata = MetaData()

    try:
        market_data_table = Table("market_data", metadata, autoload_with=engine)
    except Exception as exc:
        logger.error(
            "La table 'market_data' n'existe pas ou n'est pas accessible. "
            "Assurez-vous que le backend a initialisé la base de données : %s", exc
        )
        raise

    # Conversion du DataFrame en liste de dictionnaires pour SQLAlchemy
    records = df.to_dict(orient="records")

    # 4. Insertion avec gestion de conflit (Upsert)
    if engine.dialect.name == "postgresql":
        # Dialecte natif PostgreSQL : clause ON CONFLICT DO UPDATE
        stmt = insert(market_data_table).values(records)

        # Liste des colonnes à mettre à jour en cas de conflit (on exclut la clé primaire et la date de création)
        update_cols = {
            col.name: stmt.excluded[col.name]
            for col in market_data_table.columns
            if col.name not in ["id", "created_at", "symbol", "exchange", "interval_timeframe", "open_time"]
        }
        # Forcer la mise à jour de updated_at
        update_cols["updated_at"] = stmt.excluded.updated_at

        upsert_stmt = stmt.on_conflict_do_update(
            constraint="uq_market_data_symbol_time",
            set_=update_cols
        )

        with engine.begin() as conn:
            conn.execute(upsert_stmt)
            logger.info("Upsert (PostgreSQL) terminé avec succès pour %s lignes.", len(records))
    else:
        # Fallback pour les autres dialectes (ex: SQLite pour le développement local)
        # Supprime et insère pour simuler l'upsert de façon idempotente
        logger.info("Dialecte '%s' détecté, exécution du fallback idempotente (Delete-then-Insert)", engine.dialect.name)
        with engine.begin() as conn:
            for record in records:
                # Suppression
                conn.execute(
                    market_data_table.delete().where(
                        market_data_table.c.symbol == record["symbol"],
                        market_data_table.c.exchange == record["exchange"],
                        market_data_table.c.interval_timeframe == record["interval_timeframe"],
                        market_data_table.c.open_time == record["open_time"]
                    )
                )
                # Insertion
                conn.execute(market_data_table.insert().values(record))
            logger.info("Chargement fallback terminé avec succès pour %s lignes.", len(records))


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def run_loading(object_key: str, bucket: str = MINIO_BUCKET, db_url: str = DATABASE_URL) -> None:
    """Télécharge le fichier de MinIO et le charge dans PostgreSQL."""
    df = download_parquet_dataframe(object_key, bucket)
    transform_and_load(df, db_url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Charge les données OHLCV depuis MinIO dans PostgreSQL."
    )
    parser.add_argument("--object-key", required=True, help="Clé de l'objet Parquet dans MinIO")
    parser.add_argument("--bucket", default=MINIO_BUCKET, help="Bucket MinIO source")
    parser.add_argument("--db-url", default=DATABASE_URL, help="URL de connexion à la base de données")
    args = parser.parse_args()

    try:
        run_loading(object_key=args.object_key, bucket=args.bucket, db_url=args.db_url)
        print("✓ Données chargées avec succès dans la base de données.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Échec du chargement : %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
