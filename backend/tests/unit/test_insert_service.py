"""
Tests unitaires pour src/market/insert_service.py (issue #13).

La collecte (driver) et le stockage objet (MinIO) sont mockes ; la session DB est un
MagicMock (le statement UPSERT est du dialecte PostgreSQL, non exercable via SQLite).
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


def _kline_row(
    *,
    symbol="BTCUSDT",
    source="binance",
    interval="1h",
    open_time=None,
    quote_asset_volume=1000.0,
    number_of_trades=42,
    taker_buy_base_volume=0.5,
    taker_buy_quote_volume=500.0,
):
    """Construit une ligne OHLCV normalisee, telle que renvoyee par un MarketDataDriver."""
    open_time = open_time or datetime(2026, 1, 1, tzinfo=UTC)
    return {
        "symbol": symbol,
        "interval": interval,
        "source": source,
        "open_time": open_time,
        "open": 100.0,
        "high": 110.0,
        "low": 90.0,
        "close": 105.0,
        "volume": 12.5,
        "close_time": datetime(2026, 1, 1, 0, 59, tzinfo=UTC),
        "quote_asset_volume": quote_asset_volume,
        "number_of_trades": number_of_trades,
        "taker_buy_base_volume": taker_buy_base_volume,
        "taker_buy_quote_volume": taker_buy_quote_volume,
    }


@pytest.fixture
def mock_minio():
    with patch("market.insert_service.ClientMinIO") as mock_cls:
        instance = mock_cls.return_value
        instance.default_bucket = "crypto-bot-data"
        instance.upload_dataframe.return_value = True
        yield instance


@pytest.fixture
def service(mock_minio):
    from market.insert_service import MarketDataInsertService

    return MarketDataInsertService(db=MagicMock())


class TestInsertHistoricalData:
    """insert_historical_data() : orchestration collecte -> MinIO -> DB."""

    def test_invalid_interval_raises_before_any_fetch(self, service):
        with patch("market.insert_service.get_market_data_driver") as mock_get_driver:
            with pytest.raises(ValueError, match="Invalid interval"):
                service.insert_historical_data(
                    exchange="binance",
                    symbol="BTCUSDT",
                    interval="3m",
                    start_time=datetime(2026, 1, 1, tzinfo=UTC),
                )
        mock_get_driver.assert_not_called()

    def test_no_data_returns_zeroed_stats_without_touching_minio_or_db(self, service, mock_minio):
        mock_driver = MagicMock()
        mock_driver.fetch_klines.return_value = []

        with patch("market.insert_service.get_market_data_driver", return_value=mock_driver):
            result = service.insert_historical_data(
                exchange="kraken",
                symbol="BTCEUR",
                interval="1h",
                start_time=datetime(2026, 1, 1, tzinfo=UTC),
            )

        assert result == {"inserted": 0, "updated": 0, "failed": 0, "total": 0}
        mock_minio.upload_dataframe.assert_not_called()
        service.db.execute.assert_not_called()

    def test_resolves_driver_for_requested_exchange_and_forwards_time_range(self, service):
        mock_driver = MagicMock()
        mock_driver.fetch_klines.return_value = [_kline_row(source="kraken", symbol="BTCEUR")]
        start_time = datetime(2026, 1, 1, tzinfo=UTC)
        end_time = datetime(2026, 1, 2, tzinfo=UTC)

        with patch("market.insert_service.get_market_data_driver", return_value=mock_driver) as mock_get_driver:
            service.insert_historical_data(
                exchange="kraken",
                symbol="BTCEUR",
                interval="1h",
                start_time=start_time,
                end_time=end_time,
                limit=500,
            )

        mock_get_driver.assert_called_once_with("kraken")
        mock_driver.fetch_klines.assert_called_once_with(
            "BTCEUR",
            "1h",
            limit=500,
            start_time_ms=int(start_time.timestamp() * 1000),
            end_time_ms=int(end_time.timestamp() * 1000),
        )

    def test_defaults_end_time_to_now_when_not_provided(self, service):
        mock_driver = MagicMock()
        mock_driver.fetch_klines.return_value = []

        with patch("market.insert_service.get_market_data_driver", return_value=mock_driver):
            with patch("market.insert_service.datetime") as mock_datetime:
                mock_datetime.now.return_value = datetime(2026, 6, 1, tzinfo=UTC)
                mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
                service.insert_historical_data(
                    exchange="binance",
                    symbol="BTCUSDT",
                    interval="1h",
                    start_time=datetime(2026, 1, 1, tzinfo=UTC),
                )

        _, kwargs = mock_driver.fetch_klines.call_args
        assert kwargs["end_time_ms"] == int(datetime(2026, 6, 1, tzinfo=UTC).timestamp() * 1000)

    def test_fetch_error_is_logged_and_re_raised(self, service, mock_minio):
        mock_driver = MagicMock()
        mock_driver.fetch_klines.side_effect = RuntimeError("boom")

        with patch("market.insert_service.get_market_data_driver", return_value=mock_driver):
            with pytest.raises(RuntimeError, match="boom"):
                service.insert_historical_data(
                    exchange="binance",
                    symbol="BTCUSDT",
                    interval="1h",
                    start_time=datetime(2026, 1, 1, tzinfo=UTC),
                )
        mock_minio.upload_dataframe.assert_not_called()


class TestSaveToMinio:
    """_save_to_minio() : chemin scope par exchange, JSON + CSV."""

    def test_object_keys_are_scoped_by_exchange(self, service, mock_minio):
        rows = [_kline_row(source="kraken", symbol="BTCEUR")]

        service._save_to_minio(
            "kraken",
            "BTCEUR",
            "1h",
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
            rows,
        )

        json_call = mock_minio.client.put_object.call_args
        assert json_call.kwargs["object_name"].startswith("market_data/kraken/BTCEUR/1h/raw_")

        csv_call = mock_minio.upload_dataframe.call_args
        assert csv_call.kwargs["object_name"].startswith("market_data/kraken/BTCEUR/1h/ohlcv_")

    def test_returns_false_and_logs_on_minio_error(self, service, mock_minio):
        mock_minio.client.put_object.side_effect = RuntimeError("minio down")

        result = service._save_to_minio(
            "binance",
            "BTCUSDT",
            "1h",
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
            [_kline_row()],
        )

        assert result is False


class TestInsertRowsToDb:
    """_insert_rows_to_db() : upsert PostgreSQL a partir de lignes normalisees."""

    def test_uses_row_source_as_exchange_not_a_hardcoded_value(self, service):
        rows = [_kline_row(source="kraken", symbol="BTCEUR")]
        service.db.execute.return_value.rowcount = 1

        service._insert_rows_to_db(rows)

        stmt = service.db.execute.call_args[0][0]
        compiled_params = stmt.compile().params
        assert compiled_params["exchange"] == "kraken"
        assert compiled_params["symbol"] == "BTCEUR"

    def test_decimal_fields_are_converted_from_normalised_row(self, service):
        rows = [_kline_row()]
        service.db.execute.return_value.rowcount = 1

        service._insert_rows_to_db(rows)

        stmt = service.db.execute.call_args[0][0]
        params = stmt.compile().params
        assert params["open_price"] == Decimal("100.0")
        assert params["quote_asset_volume"] == Decimal("1000.0")

    def test_none_optional_fields_stay_none(self, service):
        rows = [_kline_row(quote_asset_volume=None, taker_buy_base_volume=None, taker_buy_quote_volume=None)]
        service.db.execute.return_value.rowcount = 1

        service._insert_rows_to_db(rows)

        params = service.db.execute.call_args[0][0].compile().params
        assert params["quote_asset_volume"] is None
        assert params["taker_buy_base_volume"] is None
        assert params["taker_buy_quote_volume"] is None

    def test_stats_count_inserted_vs_failed(self, service):
        rows = [_kline_row(), _kline_row()]
        service.db.execute.side_effect = [MagicMock(rowcount=1), RuntimeError("db down")]

        result = service._insert_rows_to_db(rows)

        assert result == {"inserted": 1, "updated": 0, "failed": 1, "total": 2}
        service.db.rollback.assert_called_once()


class TestValidateSymbol:
    """validate_symbol() : generique via fetch_klines(limit=1), pas d'appel Binance en dur."""

    def test_valid_symbol_returns_true(self, service):
        mock_driver = MagicMock()
        mock_driver.fetch_klines.return_value = [_kline_row()]

        with patch("market.insert_service.get_market_data_driver", return_value=mock_driver) as mock_get_driver:
            assert service.validate_symbol("kraken", "BTCEUR") is True

        mock_get_driver.assert_called_once_with("kraken")
        mock_driver.fetch_klines.assert_called_once_with("BTCEUR", "1h", limit=1)

    def test_unknown_symbol_returns_false_without_raising(self, service):
        mock_driver = MagicMock()
        mock_driver.fetch_klines.side_effect = ValueError("Unknown quote in symbol: NOTAPAIR")

        with patch("market.insert_service.get_market_data_driver", return_value=mock_driver):
            assert service.validate_symbol("binance", "NOTAPAIR") is False


class TestGetDataCount:
    """get_data_count() : filtre optionnel par exchange (un symbole peut exister sur plusieurs)."""

    def test_filters_by_exchange_when_provided(self, service):
        query = service.db.query.return_value
        filtered_by_base = query.filter.return_value
        filtered_by_exchange = filtered_by_base.filter.return_value
        filtered_by_exchange.count.return_value = 3

        count = service.get_data_count(
            "BTCUSDT", "1h", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC), exchange="Kraken"
        )

        assert count == 3
        filtered_by_base.filter.assert_called_once()

    def test_no_exchange_filter_when_omitted(self, service):
        query = service.db.query.return_value
        filtered = query.filter.return_value
        filtered.count.return_value = 5

        count = service.get_data_count("BTCUSDT", "1h", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC))

        assert count == 5
        filtered.filter.assert_not_called()

    def test_returns_zero_and_logs_on_db_error(self, service):
        service.db.query.side_effect = RuntimeError("db down")

        assert service.get_data_count("BTCUSDT", "1h", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)) == 0


class TestGetLatestData:
    """get_latest_data() : lecture DB, filtre optionnel par exchange."""

    def _mock_record(self, exchange="binance"):
        record = MagicMock()
        record.id = 1
        record.symbol = "BTCUSDT"
        record.exchange = exchange
        record.interval_timeframe = "1h"
        record.open_time = datetime(2026, 1, 1, tzinfo=UTC)
        record.close_time = datetime(2026, 1, 1, 0, 59, tzinfo=UTC)
        record.open_price = Decimal("100")
        record.high_price = Decimal("110")
        record.low_price = Decimal("90")
        record.close_price = Decimal("105")
        record.volume = Decimal("12.5")
        record.quote_asset_volume = Decimal("1000")
        record.number_of_trades = 42
        record.taker_buy_base_volume = Decimal("0.5")
        record.taker_buy_quote_volume = Decimal("500")
        return record

    def test_returns_records_as_dicts(self, service):
        query = service.db.query.return_value
        filtered = query.filter.return_value
        ordered = filtered.order_by.return_value
        ordered.limit.return_value.all.return_value = [self._mock_record()]

        data = service.get_latest_data("BTCUSDT", "1h", limit=10)

        assert len(data) == 1
        assert data[0]["symbol"] == "BTCUSDT"
        assert data[0]["open_price"] == 100.0

    def test_filters_by_exchange_when_provided(self, service):
        query = service.db.query.return_value
        filtered_by_base = query.filter.return_value
        filtered_by_exchange = filtered_by_base.filter.return_value
        filtered_by_exchange.order_by.return_value.limit.return_value.all.return_value = []

        service.get_latest_data("BTCUSDT", "1h", limit=10, exchange="binance")

        filtered_by_base.filter.assert_called_once()

    def test_returns_empty_list_and_logs_on_db_error(self, service):
        service.db.query.side_effect = RuntimeError("db down")

        assert service.get_latest_data("BTCUSDT", "1h") == []
