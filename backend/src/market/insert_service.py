"""
Service for inserting historical market data into PostgreSQL and MinIO.
This service fetches OHLCV data through the shared multi-exchange market data
driver (utils.connectors.exchanges) and persists it to the database and object storage.
"""

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from market.clients.minio import ClientMinIO
from market.models import MarketData
from utils.connectors.exchanges import get_market_data_driver

logger = logging.getLogger(__name__)

# Intervalles supportes par les drivers de donnees de marche (natif Binance et ccxt)
ALLOWED_INTERVALS = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"}


class MarketDataInsertService:
    """
    Service for inserting historical market data from any registered exchange.
    Handles data fetching, validation, and persistence.
    """

    def __init__(self, db: Session):
        """
        Initialize the service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.minio_client = ClientMinIO()

    def insert_historical_data(
        self,
        exchange: str,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> dict:
        """
        Fetch historical data from the given exchange and insert into database.

        Args:
            exchange: Exchange source (e.g. 'binance', 'kraken') — resolved via the registry
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Time interval (e.g., '1h', '4h', '1d')
            start_time: Start datetime for historical data
            end_time: End datetime (default: now)
            limit: Maximum number of records to fetch (default: 1000)

        Returns:
            dict: Statistics about the insertion (inserted, updated, failed)
        """
        if interval.lower() not in ALLOWED_INTERVALS:
            raise ValueError(f"Invalid interval: {interval}")

        if end_time is None:
            end_time = datetime.now(UTC)

        logger.info(
            f"Fetching historical data for {exchange}:{symbol} ({interval}) "
            f"from {start_time} to {end_time}, limit={limit}"
        )

        rows = self._fetch_klines(exchange, symbol, interval, start_time, end_time, limit)

        if not rows:
            logger.warning(f"No data received from {exchange} for {symbol}")
            return {"inserted": 0, "updated": 0, "failed": 0, "total": 0}

        # Save raw data to MinIO
        self._save_to_minio(exchange, symbol, interval, start_time, end_time, rows)

        # Insert data into database
        result = self._insert_rows_to_db(rows)

        logger.info(
            f"Data insertion complete for {exchange}:{symbol}: "
            f"{result['inserted']} inserted, {result['updated']} updated, "
            f"{result['failed']} failed out of {result['total']} total"
        )

        return result

    def _fetch_klines(
        self,
        exchange: str,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        limit: int,
    ) -> list[dict]:
        """
        Fetch normalised OHLCV rows from the exchange's market data driver.

        Args:
            exchange: Exchange source (e.g. 'binance', 'kraken')
            symbol: Trading pair symbol
            interval: Time interval
            start_time: Start datetime
            end_time: End datetime
            limit: Maximum number of records

        Returns:
            List of normalised OHLCV dicts (see utils.connectors.exchanges.base.normalize_ohlcv)
        """
        try:
            driver = get_market_data_driver(exchange)
            rows = driver.fetch_klines(
                symbol,
                interval,
                limit=limit,
                start_time_ms=int(start_time.timestamp() * 1000),
                end_time_ms=int(end_time.timestamp() * 1000),
            )
            logger.info(f"Fetched {len(rows)} klines from {exchange} for {symbol}")
            return rows

        except Exception as e:
            logger.error(f"Error fetching data from {exchange}: {e!s}")
            raise

    def _save_to_minio(
        self,
        exchange: str,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        rows: list[dict],
    ) -> bool:
        """
        Save normalised OHLCV rows to MinIO in JSON and CSV formats.

        Args:
            exchange: Exchange source (e.g. 'binance', 'kraken')
            symbol: Trading pair symbol
            interval: Time interval
            start_time: Start datetime
            end_time: End datetime
            rows: List of normalised OHLCV dicts

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Generate timestamp for filename
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

            # Generate folder structure: market_data/{exchange}/{symbol}/{interval}/
            folder_prefix = f"market_data/{exchange.lower()}/{symbol}/{interval}"

            # 1. Save as JSON (normalised format)
            json_filename = f"{folder_prefix}/raw_{timestamp}.json"
            json_data = {
                "exchange": exchange,
                "symbol": symbol,
                "interval": interval,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "count": len(rows),
                "data": rows,
                "fetched_at": datetime.now(UTC).isoformat(),
            }

            # Convert to JSON string
            json_str = json.dumps(json_data, indent=2, default=str)
            json_bytes = json_str.encode("utf-8")

            # Upload JSON to MinIO
            from io import BytesIO

            json_buffer = BytesIO(json_bytes)
            json_buffer.seek(0)

            self.minio_client.client.put_object(
                bucket_name=self.minio_client.default_bucket,
                object_name=json_filename,
                data=json_buffer,
                length=len(json_bytes),
                content_type="application/json",
            )
            logger.info(f"✅ JSON saved to MinIO: {json_filename}")

            # 2. Save as CSV (formatted OHLCV data)
            csv_filename = f"{folder_prefix}/ohlcv_{timestamp}.csv"

            df = pd.DataFrame(rows)

            # Upload CSV using the minio_client method
            success = self.minio_client.upload_dataframe(df=df, object_name=csv_filename, format="csv")

            if success:
                logger.info(f"✅ CSV saved to MinIO: {csv_filename}")
            else:
                logger.warning(f"⚠️  Failed to save CSV to MinIO: {csv_filename}")

            return True

        except Exception as e:
            logger.error(f"❌ Error saving data to MinIO: {e!s}")
            return False

    def _insert_rows_to_db(self, rows: list[dict]) -> dict:
        """
        Insert normalised OHLCV rows into PostgreSQL database with upsert logic.

        Args:
            rows: List of normalised OHLCV dicts (see utils.connectors.exchanges.base.normalize_ohlcv)

        Returns:
            dict: Statistics about the insertion
        """
        inserted = 0
        updated = 0
        failed = 0
        total = len(rows)

        for row in rows:
            try:
                quote_asset_volume = row["quote_asset_volume"]
                taker_buy_base_volume = row["taker_buy_base_volume"]
                taker_buy_quote_volume = row["taker_buy_quote_volume"]

                market_data = {
                    "symbol": row["symbol"],
                    "exchange": row["source"],
                    "interval_timeframe": row["interval"],
                    "open_time": row["open_time"],
                    "open_price": Decimal(str(row["open"])),
                    "high_price": Decimal(str(row["high"])),
                    "low_price": Decimal(str(row["low"])),
                    "close_price": Decimal(str(row["close"])),
                    "volume": Decimal(str(row["volume"])),
                    "close_time": row["close_time"],
                    "quote_asset_volume": (
                        Decimal(str(quote_asset_volume)) if quote_asset_volume is not None else None
                    ),
                    "number_of_trades": row["number_of_trades"],
                    "taker_buy_base_volume": (
                        Decimal(str(taker_buy_base_volume)) if taker_buy_base_volume is not None else None
                    ),
                    "taker_buy_quote_volume": (
                        Decimal(str(taker_buy_quote_volume)) if taker_buy_quote_volume is not None else None
                    ),
                }

                # Use PostgreSQL UPSERT to insert or update
                stmt = insert(MarketData).values(**market_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[
                        "symbol",
                        "exchange",
                        "interval_timeframe",
                        "open_time",
                    ],
                    set_={
                        "open_price": stmt.excluded.open_price,
                        "high_price": stmt.excluded.high_price,
                        "low_price": stmt.excluded.low_price,
                        "close_price": stmt.excluded.close_price,
                        "volume": stmt.excluded.volume,
                        "close_time": stmt.excluded.close_time,
                        "quote_asset_volume": stmt.excluded.quote_asset_volume,
                        "number_of_trades": stmt.excluded.number_of_trades,
                        "taker_buy_base_volume": stmt.excluded.taker_buy_base_volume,
                        "taker_buy_quote_volume": stmt.excluded.taker_buy_quote_volume,
                        "updated_at": datetime.now(UTC),
                    },
                )

                result = self.db.execute(stmt)
                self.db.commit()

                # Check if it was an insert or update
                if result.rowcount > 0:
                    # Note: Can't easily distinguish insert vs update with ON CONFLICT
                    # For simplicity, count all as inserts
                    inserted += 1
                else:
                    updated += 1

            except Exception as e:
                logger.error(f"Error inserting kline: {e!s}")
                self.db.rollback()
                failed += 1
                continue

        return {
            "inserted": inserted,
            "updated": updated,
            "failed": failed,
            "total": total,
        }

    def get_data_count(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        exchange: str | None = None,
    ) -> int:
        """
        Get count of existing records in the database for the given parameters.

        Args:
            symbol: Trading pair symbol
            interval: Time interval
            start_time: Start datetime
            end_time: End datetime
            exchange: Restrict the count to this exchange (a symbol can exist on several)

        Returns:
            int: Number of existing records
        """
        try:
            query = self.db.query(MarketData).filter(
                MarketData.symbol == symbol,
                MarketData.interval_timeframe == interval,
                MarketData.open_time >= start_time,
                MarketData.open_time <= end_time,
            )
            if exchange:
                query = query.filter(MarketData.exchange == exchange.lower())
            return query.count()
        except Exception as e:
            logger.error(f"Error counting records: {e!s}")
            return 0

    def validate_symbol(self, exchange: str, symbol: str) -> bool:
        """
        Validate if a symbol exists on the given exchange.

        No dedicated "symbol info" endpoint is exposed by the market data driver
        contract, so validation fetches a single kline: it fails the same way
        (invalid symbol/pair) on both the native and ccxt drivers.

        Args:
            exchange: Exchange source (e.g. 'binance', 'kraken')
            symbol: Trading pair symbol

        Returns:
            bool: True if symbol is valid
        """
        try:
            driver = get_market_data_driver(exchange)
            driver.fetch_klines(symbol, "1h", limit=1)
            return True
        except Exception as e:
            logger.warning(f"Symbol validation failed for {exchange}:{symbol}: {e!s}")
            return False

    def get_latest_data(self, symbol: str, interval: str, limit: int = 100, exchange: str | None = None) -> list[dict]:
        """
        Retrieve the latest market data from PostgreSQL database.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Time interval (e.g., '1h', '4h', '1d')
            limit: Maximum number of records to retrieve (default: 100)
            exchange: Restrict to this exchange (a symbol can exist on several)

        Returns:
            List[dict]: List of market data records ordered by time (most recent first)
        """
        try:
            # Query database for latest records
            query = self.db.query(MarketData).filter(
                MarketData.symbol == symbol,
                MarketData.interval_timeframe == interval,
            )
            if exchange:
                query = query.filter(MarketData.exchange == exchange.lower())
            records = query.order_by(MarketData.open_time.desc()).limit(limit).all()

            # Convert ORM objects to dictionaries
            data_list = []
            for record in records:
                data_list.append(
                    {
                        "id": record.id,
                        "symbol": record.symbol,
                        "exchange": record.exchange,
                        "interval_timeframe": record.interval_timeframe,
                        "open_time": record.open_time,
                        "close_time": record.close_time,
                        "open_price": float(record.open_price),
                        "high_price": float(record.high_price),
                        "low_price": float(record.low_price),
                        "close_price": float(record.close_price),
                        "volume": float(record.volume),
                        "quote_asset_volume": (float(record.quote_asset_volume) if record.quote_asset_volume else None),
                        "number_of_trades": record.number_of_trades,
                        "taker_buy_base_volume": (
                            float(record.taker_buy_base_volume) if record.taker_buy_base_volume else None
                        ),
                        "taker_buy_quote_volume": (
                            float(record.taker_buy_quote_volume) if record.taker_buy_quote_volume else None
                        ),
                    }
                )

            logger.info(f"Retrieved {len(data_list)} records for {symbol} ({interval})")
            return data_list

        except Exception as e:
            logger.error(f"Error retrieving data from database: {e!s}")
            return []
