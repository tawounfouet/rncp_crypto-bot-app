"""
Database connection management for the crypto trading bot.

This module handles database connections, session management, and provides
automatic fallback from PostgreSQL to SQLite for development environments.
"""

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from shared.config.settings import get_settings
from shared.models.base import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections with automatic PostgreSQL to SQLite fallback.

    Features:
    - Automatic environment detection (Docker vs local)
    - PostgreSQL to SQLite fallback mechanism
    - Connection testing and validation
    - Session management with context managers
    - Table creation and initialization
    """

    def __init__(self):
        self.settings = get_settings()
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None
        self._database_url: str | None = None

    def _get_postgresql_url(self) -> str | None:
        """Construct PostgreSQL URL from environment variables."""
        try:
            # Use settings values directly for consistency
            if self.settings.IS_DOCKER:
                # In Docker: use service name
                host = self.settings.POSTGRES_HOST or "postgres"
                port = self.settings.POSTGRES_PORT or 5432
            else:
                # Local development: use configured values (typically localhost:5434)
                host = self.settings.POSTGRES_HOST or "localhost"
                port = self.settings.POSTGRES_PORT or 5434

            user = self.settings.POSTGRES_USER
            password = self.settings.POSTGRES_PWD
            db_name = self.settings.POSTGRES_DB

            if all([user, password, db_name]):
                url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
                logger.info(f"Constructed PostgreSQL URL for host: {host}:{port}")
                return url
            else:
                logger.warning("Missing PostgreSQL configuration in settings")
                return None

        except Exception as e:
            logger.error(f"Error constructing PostgreSQL URL: {e}")
            return None

    def _get_sqlite_url(self) -> str:
        """Get SQLite database URL with proper path handling."""
        # Get the backend directory (where this file is located)
        backend_dir = os.path.dirname(os.path.dirname(__file__))

        # Use the SQLITE_DB_PATH from settings (default: db.sqlite3)
        db_path = os.path.join(backend_dir, self.settings.SQLITE_DB_PATH)
        sqlite_url = f"sqlite:///{db_path}"
        logger.info(f"Using SQLite database at: {db_path}")
        return sqlite_url

    def _test_connection(self, url: str) -> bool:
        """Test if database connection is working."""
        try:
            test_engine = create_engine(url, echo=False)
            with test_engine.connect() as conn:
                # Test basic connection
                conn.execute(text("SELECT 1"))
                logger.info(f"Database connection test successful for: {url.split('@')[0]}@...")
                return True
        except Exception as e:
            logger.warning(f"Database connection test failed: {e}")
            return False

    def get_database_url(self) -> str:
        """
        Get database URL with automatic fallback logic.

        Priority:
        1. Explicit DATABASE_URL environment variable
        2. PostgreSQL from environment variables
        3. SQLite fallback
        """
        if self._database_url:
            return self._database_url

        # 1. Check for explicit DATABASE_URL
        explicit_url = os.getenv("DATABASE_URL")
        if explicit_url:
            if self._test_connection(explicit_url):
                self._database_url = explicit_url
                logger.info("Using explicit DATABASE_URL")
                return explicit_url
            else:
                logger.warning("Explicit DATABASE_URL failed, trying alternatives")

        # 2. Try PostgreSQL
        pg_url = self._get_postgresql_url()
        if pg_url and self._test_connection(pg_url):
            self._database_url = pg_url
            logger.info("Using PostgreSQL database")
            return pg_url

        # 3. Fallback to SQLite
        sqlite_url = self._get_sqlite_url()
        self._database_url = sqlite_url
        logger.info("Falling back to SQLite database")
        return sqlite_url

    def get_engine(self) -> Engine:
        """Get or create database engine."""
        if self._engine is None:
            database_url = self.get_database_url()

            # Configure engine based on database type
            if database_url.startswith("sqlite"):
                # SQLite specific configuration
                self._engine = create_engine(
                    database_url,
                    echo=self.settings.DATABASE_ECHO,
                    pool_pre_ping=True,
                    connect_args={"check_same_thread": False},
                )
            else:
                # PostgreSQL specific configuration
                self._engine = create_engine(
                    database_url,
                    echo=self.settings.DATABASE_ECHO,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                )

            logger.info(f"Database engine created for: {database_url.split('://')[0]}")

        return self._engine

    def get_session_factory(self) -> sessionmaker:
        """Get or create session factory."""
        if self._session_factory is None:
            engine = self.get_engine()
            self._session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        return self._session_factory

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.

        Usage:
            with db_manager.get_session() as session:
                # Use session here
                pass
        """
        session_factory = self.get_session_factory()
        session = session_factory()

        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()

    def create_tables(self) -> bool:
        """
        Create all database tables.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            engine = self.get_engine()

            # Import all models to ensure they're registered

            # Create all tables
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
            return True

        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            return False

    def check_connection(self) -> bool:
        """Check if database connection is working."""
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False

    def get_database_info(self) -> dict[str, Any]:
        """Get information about the current database."""
        try:
            url = self.get_database_url()
            engine = self.get_engine()

            info = {
                "database_type": url.split("://")[0],
                "url_masked": url.split("@")[-1] if "@" in url else url,
                "engine_pool_size": getattr(engine.pool, "size", None),
                "is_connected": self.check_connection(),
            }

            return info

        except Exception as e:
            logger.error(f"Error getting database info: {e}")
            return {"error": str(e)}


# Global database manager instance
db_manager = DatabaseManager()


# Convenience functions for common operations
def get_db_session() -> Generator[Session, None, None]:
    """Get database session (convenience function)."""
    return db_manager.get_session()


def init_database() -> bool:
    """Initialize database with tables (convenience function)."""
    return db_manager.create_tables()


def get_database_info() -> dict[str, Any]:
    """Get database information (convenience function)."""
    return db_manager.get_database_info()
