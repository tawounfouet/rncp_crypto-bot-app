from __future__ import annotations

import logging
import os
from typing import Any

from sqlalchemy import Engine, create_engine

logger = logging.getLogger(__name__)


def get_database_url(
    *,
    host: str | None = None,
    port: str | int | None = None,
    user: str | None = None,
    password: str | None = None,
    db: str | None = None,
) -> str:
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit

    pg_host = host or os.environ.get("POSTGRES_HOST", "postgres")
    pg_port = port or os.environ.get("POSTGRES_PORT", "5432")
    pg_user = user or os.environ.get("POSTGRES_USER", "postgres")
    pg_pwd = password or os.environ.get("POSTGRES_PWD", "postgres")
    pg_db = db or os.environ.get("POSTGRES_DB", "crypto_bot_db")

    return f"postgresql://{pg_user}:{pg_pwd}@{pg_host}:{pg_port}/{pg_db}"


def create_db_engine(url: str | None = None, **kwargs: Any) -> Engine:
    url = url or get_database_url()
    logger.info("Creating database engine for %s", url.split("@")[-1] if "@" in url else url)

    defaults: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 3600,
    }
    defaults.update(kwargs)
    return create_engine(url, **defaults)
