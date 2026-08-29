from __future__ import annotations

import os
from io import BytesIO

import pandas as pd
from minio import Minio
from minio.error import S3Error

from utils.logging import get_logger

logger = get_logger("connectors.minio")


class MinioClient:
    """MinIO client with lazy initialisation and DataFrame helpers."""

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool | None = None,
        default_bucket: str | None = None,
    ):
        self.endpoint = endpoint or os.environ.get("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = access_key or os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = secret_key or os.environ.get("MINIO_SECRET_KEY", "minioadmin")
        if secure is not None:
            self.secure = secure
        else:
            self.secure = os.environ.get("MINIO_SECURE", "0").lower() in ("true", "1", "yes")
        self.default_bucket = default_bucket or os.environ.get("MINIO_BUCKET", "crypto-bot-data")
        self._client: Minio | None = None

    @property
    def client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
            logger.info("MinIO client ready endpoint=%s", self.endpoint)
            self._ensure_bucket(self.default_bucket)
        return self._client

    def _ensure_bucket(self, bucket: str) -> None:
        try:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
                logger.info("Bucket created bucket=%s", bucket)
        except S3Error as exc:
            logger.warning("Bucket check failed bucket=%s: %s", bucket, exc)

    # -- Files -----------------------------------------------------------------

    def upload_file(self, file_path: str, object_name: str, bucket: str | None = None) -> bool:
        bucket = bucket or self.default_bucket
        try:
            self.client.fput_object(bucket, object_name, file_path)
            logger.info("File uploaded bucket=%s key=%s", bucket, object_name)
            return True
        except S3Error as exc:
            logger.error("Upload failed bucket=%s key=%s: %s", bucket, object_name, exc)
            return False

    def download_file(self, object_name: str, file_path: str, bucket: str | None = None) -> bool:
        bucket = bucket or self.default_bucket
        try:
            self.client.fget_object(bucket, object_name, file_path)
            logger.info("File downloaded bucket=%s key=%s → %s", bucket, object_name, file_path)
            return True
        except S3Error as exc:
            logger.error("Download failed bucket=%s key=%s: %s", bucket, object_name, exc)
            return False

    # -- DataFrames ------------------------------------------------------------

    def upload_dataframe(
        self,
        df: pd.DataFrame,
        object_name: str,
        bucket: str | None = None,
        fmt: str = "parquet",
    ) -> bool:
        bucket = bucket or self.default_bucket
        buffer = BytesIO()

        try:
            if fmt == "csv":
                df.to_csv(buffer, index=False)
            elif fmt == "parquet":
                df.to_parquet(buffer, index=False)
            elif fmt == "json":
                df.to_json(buffer, orient="records")
            else:
                logger.error("Unsupported format: %s", fmt)
                return False

            buffer.seek(0)
            content_type = {
                "csv": "text/csv",
                "parquet": "application/vnd.apache.parquet",
                "json": "application/json",
            }.get(fmt, "application/octet-stream")

            self.client.put_object(bucket, object_name, buffer, buffer.getbuffer().nbytes, content_type=content_type)
            logger.info("DataFrame uploaded bucket=%s key=%s rows=%d fmt=%s", bucket, object_name, len(df), fmt)
            return True
        except Exception as exc:
            logger.error("DataFrame upload failed bucket=%s key=%s: %s", bucket, object_name, exc)
            return False

    def download_dataframe(
        self, object_name: str, bucket: str | None = None, fmt: str = "parquet"
    ) -> pd.DataFrame | None:
        bucket = bucket or self.default_bucket
        buffer = BytesIO()

        try:
            response = self.client.get_object(bucket, object_name)
            for chunk in response.stream():
                buffer.write(chunk)
            buffer.seek(0)
            response.close()
            response.release_conn()

            readers = {
                "csv": pd.read_csv,
                "parquet": pd.read_parquet,
                "json": pd.read_json,
            }
            reader = readers.get(fmt)
            if reader is None:
                logger.error("Unsupported format: %s", fmt)
                return None

            df = reader(buffer)
            logger.info("DataFrame downloaded bucket=%s key=%s rows=%d", bucket, object_name, len(df))
            return df
        except Exception as exc:
            logger.error("DataFrame download failed bucket=%s key=%s: %s", bucket, object_name, exc)
            return None

    # -- Object listing / deletion ---------------------------------------------

    def list_objects(self, prefix: str = "", bucket: str | None = None) -> list[dict]:
        bucket = bucket or self.default_bucket
        try:
            return [
                {"Key": obj.object_name, "Size": obj.size, "LastModified": obj.last_modified}
                for obj in self.client.list_objects(bucket, prefix=prefix, recursive=True)
            ]
        except S3Error as exc:
            logger.error("List objects failed bucket=%s prefix=%s: %s", bucket, prefix, exc)
            return []

    def delete_object(self, object_name: str, bucket: str | None = None) -> bool:
        bucket = bucket or self.default_bucket
        try:
            self.client.remove_object(bucket, object_name)
            logger.info("Object deleted bucket=%s key=%s", bucket, object_name)
            return True
        except S3Error as exc:
            logger.error("Delete failed bucket=%s key=%s: %s", bucket, object_name, exc)
            return False
