"""
Database package for the crypto trading bot.

This package contains all database-related functionality including:
- Connection management with automatic PostgreSQL to SQLite fallback
- Database initialization and table creation
- SQL schemas and migrations
- Database utility functions

Main components:
- connection.py: Database connection manager
- init_database.sql: Complete database schema
- migrations/: Database migration scripts
- seeds/: Test data and initial data
"""

from .connection import (
    DatabaseManager,
    db_manager,
    get_database_info,
    get_db_session,
    init_database,
)
from .dependencies import get_db

__all__ = [
    "DatabaseManager",
    "db_manager",
    "get_database_info",
    "get_db",
    "get_db_session",
    "init_database",
]
