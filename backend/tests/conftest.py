"""
Configuration pytest pour les tests du backend.

Fixtures centralisees :
- mock_settings : mock des settings applicatifs
- db_engine / db_session : base SQLite en memoire pour tests d'integration
- patch_db_session : remplace get_db_session par la session de test

Le PYTHONPATH (backend/src + racine du repo pour `utils`) est fourni par l'appelant
(make test-backend, make test-coverage, CI) -- ce fichier ne manipule plus sys.path.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from shared.models.base import Base


# =============================================================================
# Fixtures communes (unit + integration)
# =============================================================================


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock les settings pour eviter les erreurs de validation.

    Utilise autouse=True pour etre applique a TOUS les tests automatiquement.
    Les tests qui ont besoin de settings reels peuvent overrider cette fixture.
    """
    mock = MagicMock()
    mock.SECRET_KEY.get_secret_value.return_value = "test-secret-key-for-testing"  # noqa: S106
    mock.ALGORITHM = "HS256"
    mock.ACCESS_TOKEN_EXPIRE_MINUTES = 30
    mock.REFRESH_TOKEN_EXPIRE_DAYS = 7
    mock.IS_DOCKER = False
    mock.POSTGRES_HOST = "localhost"
    mock.POSTGRES_PORT = 5434
    mock.POSTGRES_USER = "test"
    mock.POSTGRES_PWD = "test"
    mock.POSTGRES_DB = "test"
    mock.DATABASE_ECHO = False
    mock.SQLITE_DB_PATH = "test.sqlite3"

    with patch("shared.config.settings.get_settings", return_value=mock):
        with patch("shared.config.settings.settings", mock):
            yield mock


# =============================================================================
# Fixtures d'integration (base de donnees SQLite en memoire)
# =============================================================================


@pytest.fixture(scope="session")
def db_engine():
    """Cree un engine SQLite en memoire pour toute la session de tests.

    Scope session pour eviter de recreer les tables a chaque test.
    L'isolation est geree par db_session (transaction rollback).
    """
    engine = create_engine("sqlite:///:memory:", echo=False)

    # SQLite: activer les foreign keys
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Importer tous les models pour les enregistrer dans Base.metadata
    import auth.models  # noqa: F401
    import market.models  # noqa: F401
    import strategy.models  # noqa: F401
    import trading.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Cree une session de test avec transaction isolee.

    Chaque test tourne dans une transaction qui est rollbackee a la fin,
    garantissant l'isolation entre tests sans recreer les tables.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def patch_db_session(db_session):
    """Remplace get_db_session partout par la session de test.

    Usage dans les tests d'integration :
        def test_something(self, patch_db_session):
            # Le service utilise automatiquement la DB de test
            service.create_user(...)

            # Verifier en BDD via patch_db_session (qui est la db_session)
            user = patch_db_session.query(User).first()
    """

    @contextmanager
    def _get_test_session():
        try:
            yield db_session
            db_session.flush()
        except Exception:
            db_session.rollback()
            raise

    with patch("auth.user_service.get_db_session", _get_test_session):
        with patch("auth.service.get_db_session", _get_test_session):
            yield db_session
