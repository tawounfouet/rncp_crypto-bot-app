"""
Database dependencies for FastAPI.
Provides database session management for route handlers.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session

from .connection import db_manager


def get_db() -> Generator[Session]:
    """
    Dependency that provides a database session for route handlers.

    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            users = db.query(User).all()
            return users

    Yields:
        Database session that will be automatically closed after use
    """
    with db_manager.get_session() as session:
        yield session
