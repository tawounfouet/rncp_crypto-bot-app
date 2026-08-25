from __future__ import annotations

import pandas as pd


class FakeMinioClient:
    def __init__(self, objects, frame=None):
        self.default_bucket = "crypto-bot-data"
        self._objects = objects
        self._frame = frame
        self.seen_prefix = None

    def list_objects(self, prefix, bucket):
        self.seen_prefix = prefix
        return self._objects

    def download_dataframe(self, object_name, bucket=None, fmt="parquet"):
        return self._frame


def test_read_raw_ohlcv_from_minio_with_exchange(monkeypatch):
    fake = FakeMinioClient(
        objects=[{"Key": "raw/ohlcv/kraken/BTCUSDC/1h/2023-01-01.parquet"}],
        frame=pd.DataFrame([{"open_time": 1, "close": 1.5}]),
    )

    monkeypatch.setattr("models.src.data.storage.MinioClient", lambda: fake)

    from models.src.data.storage import read_raw_ohlcv_from_minio

    result = read_raw_ohlcv_from_minio(symbol="BTCUSDC", interval="1h", exchange="kraken")
    assert fake.seen_prefix == "raw/ohlcv/kraken/BTCUSDC/1h/"
    assert not result.empty


def test_read_raw_ohlcv_from_minio_no_objects(monkeypatch):
    fake = FakeMinioClient(objects=[])
    monkeypatch.setattr("models.src.data.storage.MinioClient", lambda: fake)

    from models.src.data.storage import read_raw_ohlcv_from_minio

    result = read_raw_ohlcv_from_minio(exchange="kraken", symbol="BTCUSDC", interval="1h")
    assert result.empty


def test_run_ingestion_writes_exchange_scoped_key(monkeypatch):
    """Cote ecriture du couplage : run_ingestion doit produire la meme convention
    de cle que le prefixe de lecture (raw/ohlcv/{exchange}/{SYMBOL}/{interval}/...)."""
    import jobs.ingest.collect_ohlcv as ci

    class FakeDriver:
        def fetch_klines(self, symbol, interval, limit=1000):
            return [{"symbol": symbol, "interval": interval, "open_time": 1, "close": 1.5}]

    class CapturingMinio:
        def __init__(self):
            self.key = None

        def upload_dataframe(self, df, object_name, bucket=None, fmt="parquet"):
            self.key = object_name
            return True

    captured = CapturingMinio()
    monkeypatch.setattr(ci, "get_market_data_driver", lambda exchange: FakeDriver())
    monkeypatch.setattr(ci, "MinioClient", lambda: captured)

    key = ci.run_ingestion(symbol="ETHEUR", interval="1h", exchange="kraken", limit=5)

    assert key.startswith("raw/ohlcv/kraken/ETHEUR/1h/")
    assert key.endswith(".parquet")
    assert captured.key == key
