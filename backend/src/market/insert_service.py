"""
Service for inserting historical market data from Binance into PostgreSQL and MinIO.
This service handles fetching real data from Binance and persisting it to the database and object storage.
"""

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from market.clients.binance import ClientBinance
from market.clients.minio import ClientMinIO
from market.models import MarketData

logger = logging.getLogger(__name__)


class MarketDataInsertService:
    """
    Service for inserting historical market data from Binance.
    Handles data fetching, validation, and persistence.
    """

    # Mapping Binance interval strings to our format
    INTERVAL_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
    }

    def __init__(self, db: Session):
        """
        Initialize the service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.binance_client = ClientBinance()
        self.minio_client = ClientMinIO()

    def insert_historical_data(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> dict:
        """
        Fetch historical data from Binance and insert into database.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Time interval (e.g., '1h', '4h', '1d')
            start_time: Start datetime for historical data
            end_time: End datetime (default: now)
            limit: Maximum number of records to fetch (default: 1000)

        Returns:
            dict: Statistics about the insertion (inserted, updated, failed)
        """
        if end_time is None:
            end_time = datetime.now(UTC)

        logger.info(
            f"Fetching historical data for {symbol} ({interval}) " f"from {start_time} to {end_time}, limit={limit}"
        )

        # Convert interval to Binance format
        binance_interval = self._convert_interval(interval)
        if not binance_interval:
            raise ValueError(f"Invalid interval: {interval}")

        # Fetch data from Binance
        klines = self._fetch_binance_klines(symbol, binance_interval, start_time, end_time, limit)

        if not klines:
            logger.warning(f"No data received from Binance for {symbol}")
            return {"inserted": 0, "updated": 0, "failed": 0, "total": 0}

        # Save raw JSON data to MinIO
        self._save_to_minio(symbol, interval, start_time, end_time, klines)

        # Insert data into database
        result = self._insert_klines_to_db(symbol, interval, klines)

        logger.info(
            f"Data insertion complete for {symbol}: "
            f"{result['inserted']} inserted, {result['updated']} updated, "
            f"{result['failed']} failed out of {result['total']} total"
        )

        return result

    def _convert_interval(self, interval: str) -> str | None:
        """
        Convert our interval format to Binance interval format.

        Args:
            interval: Our interval string (e.g., '1h')

        Returns:
            Binance interval string or None if invalid
        """
        return self.INTERVAL_MAP.get(interval.lower())

    def _fetch_binance_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        limit: int,
    ) -> list:
        """
        Fetch klines data from Binance.

        Args:
            symbol: Trading pair symbol
            interval: Binance interval string
            start_time: Start datetime
            end_time: End datetime
            limit: Maximum number of records

        Returns:
            List of klines data from Binance
        """
        try:
            # Convert datetime to milliseconds timestamp
            start_str = int(start_time.timestamp() * 1000)
            end_str = int(end_time.timestamp() * 1000)

            # Fetch historical klines from Binance
            klines = self.binance_client.client.get_historical_klines(
                symbol=symbol,
                interval=interval,
                start_str=start_str,
                end_str=end_str,
                limit=limit,
            )

            logger.info(f"Fetched {len(klines)} klines from Binance for {symbol}")
            return klines

        except Exception as e:
            logger.error(f"Error fetching data from Binance: {e!s}")
            raise

    def _save_to_minio(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        klines: list,
    ) -> bool:
        """
        Save klines data to MinIO in JSON and CSV formats.

        Args:
            symbol: Trading pair symbol
            interval: Time interval
            start_time: Start datetime
            end_time: End datetime
            klines: List of klines from Binance

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Generate timestamp for filename
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

            # Generate folder structure: market_data/{symbol}/{interval}/
            folder_prefix = f"market_data/{symbol}/{interval}"

            # 1. Save as JSON (raw Binance format)
            json_filename = f"{folder_prefix}/raw_{timestamp}.json"
            json_data = {
                "symbol": symbol,
                "interval": interval,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "count": len(klines),
                "data": klines,
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

            # Convert klines to DataFrame
            df_data = []
            for kline in klines:
                df_data.append(
                    {
                        "open_time": datetime.fromtimestamp(kline[0] / 1000, tz=UTC).isoformat(),
                        "open": float(kline[1]),
                        "high": float(kline[2]),
                        "low": float(kline[3]),
                        "close": float(kline[4]),
                        "volume": float(kline[5]),
                        "close_time": datetime.fromtimestamp(kline[6] / 1000, tz=UTC).isoformat(),
                        "quote_asset_volume": float(kline[7]),
                        "number_of_trades": int(kline[8]),
                        "taker_buy_base_volume": float(kline[9]),
                        "taker_buy_quote_volume": float(kline[10]),
                    }
                )

            df = pd.DataFrame(df_data)

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

    def _insert_klines_to_db(self, symbol: str, interval: str, klines: list) -> dict:
        """
        Insert klines data into PostgreSQL database with upsert logic.

        Args:
            symbol: Trading pair symbol
            interval: Time interval
            klines: List of klines from Binance

        Returns:
            dict: Statistics about the insertion
        """
        inserted = 0
        updated = 0
        failed = 0
        total = len(klines)

        for kline in klines:
            try:
                # Parse Binance kline data
                # Kline format: [open_time, open, high, low, close, volume, close_time, ...]
                market_data = {
                    "symbol": symbol,
                    "exchange": "binance",
                    "interval_timeframe": interval,
                    "open_time": datetime.fromtimestamp(kline[0] / 1000, tz=UTC),
                    "open_price": Decimal(str(kline[1])),
                    "high_price": Decimal(str(kline[2])),
                    "low_price": Decimal(str(kline[3])),
                    "close_price": Decimal(str(kline[4])),
                    "volume": Decimal(str(kline[5])),
                    "close_time": datetime.fromtimestamp(kline[6] / 1000, tz=UTC),
                    "quote_asset_volume": Decimal(str(kline[7])),
                    "number_of_trades": int(kline[8]),
                    "taker_buy_base_volume": Decimal(str(kline[9])),
                    "taker_buy_quote_volume": Decimal(str(kline[10])),
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

    def get_data_count(self, symbol: str, interval: str, start_time: datetime, end_time: datetime) -> int:
        """
        Get count of existing records in the database for the given parameters.

        Args:
            symbol: Trading pair symbol
            interval: Time interval
            start_time: Start datetime
            end_time: End datetime

        Returns:
            int: Number of existing records
        """
        try:
            count = (
                self.db.query(MarketData)
                .filter(
                    MarketData.symbol == symbol,
                    MarketData.interval_timeframe == interval,
                    MarketData.open_time >= start_time,
                    MarketData.open_time <= end_time,
                )
                .count()
            )
            return count
        except Exception as e:
            logger.error(f"Error counting records: {e!s}")
            return 0

    def validate_symbol(self, symbol: str) -> bool:
        """
        Validate if a symbol exists on Binance.

        Args:
            symbol: Trading pair symbol

        Returns:
            bool: True if symbol is valid
        """
        try:
            info = self.binance_client.client.get_symbol_info(symbol)
            return info is not None
        except Exception as e:
            logger.warning(f"Symbol validation failed for {symbol}: {e!s}")
            return False

    def get_latest_data(self, symbol: str, interval: str, limit: int = 100) -> list[dict]:
        """
        Retrieve the latest market data from PostgreSQL database.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Time interval (e.g., '1h', '4h', '1d')
            limit: Maximum number of records to retrieve (default: 100)

        Returns:
            List[dict]: List of market data records ordered by time (most recent first)
        """
        try:
            # Query database for latest records
            records = (
                self.db.query(MarketData)
                .filter(
                    MarketData.symbol == symbol,
                    MarketData.interval_timeframe == interval,
                )
                .order_by(MarketData.open_time.desc())
                .limit(limit)
                .all()
            )

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
