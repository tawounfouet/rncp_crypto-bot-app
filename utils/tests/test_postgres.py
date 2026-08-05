"""Tests du connecteur Postgres partagé (utils/connectors/postgres.py)."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from utils.connectors.postgres import create_db_engine, get_database_url


class TestGetDatabaseUrl:
    def test_explicit_database_url_wins(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@z:1/db")
        assert get_database_url() == "postgresql://x:y@z:1/db"

    def test_built_from_env_defaults(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("POSTGRES_HOST", raising=False)
        monkeypatch.delenv("POSTGRES_PORT", raising=False)
        monkeypatch.delenv("POSTGRES_USER", raising=False)
        monkeypatch.delenv("POSTGRES_PWD", raising=False)
        monkeypatch.delenv("POSTGRES_DB", raising=False)
        assert get_database_url() == "postgresql://postgres:postgres@postgres:5432/crypto_bot_db"

    def test_explicit_kwargs_override_env(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        url = get_database_url(host="h", port=1234, user="u", password="p", db="d")
        assert url == "postgresql://u:p@h:1234/d"


class TestCreateDbEngine:
    def test_returns_sqlalchemy_engine(self, monkeypatch):
        # Verifie l'import `from sqlalchemy.engine import Engine` (cf. fix session
        # Airflow : `from sqlalchemy import Engine` n'existe qu'en SQLAlchemy 2.0,
        # cassait tous les DAGs sous l'image Airflow 2.8.1 -> SQLAlchemy 1.4.51).
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
        engine = create_db_engine()
        assert isinstance(engine, Engine)

    def test_custom_pool_kwargs_override_defaults(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
        engine = create_db_engine(pool_size=1)
        assert engine.pool.size() == 1
