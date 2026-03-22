"""
Tests unitaires pour services/auth_service.py
"""

import pytest
from unittest.mock import MagicMock, patch


# Mock des settings AVANT l'import du module
@pytest.fixture(autouse=True)
def mock_settings():
    """Mock les settings pour éviter les erreurs de validation."""
    mock_settings = MagicMock()
    mock_settings.SECRET_KEY.get_secret_value.return_value = "test-secret-key-for-testing"
    mock_settings.ALGORITHM = "HS256"
    mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30
    mock_settings.REFRESH_TOKEN_EXPIRE_DAYS = 7

    with patch("src.shared.config.settings.get_settings", return_value=mock_settings):
        with patch("src.shared.config.settings.settings", mock_settings):
            yield mock_settings


class TestAuthServicePasswordHashing:
    """Tests pour le hachage de mots de passe."""

    def test_get_password_hash_returns_hash(self, mock_settings):
        """Le hash retourné est différent du mot de passe original."""
        from src.auth.service import AuthService

        auth = AuthService()
        password = "TestPassword123!"
        hashed = auth.get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$argon2")  # argon2 format

    def test_verify_password_correct(self, mock_settings):
        """Vérification réussie avec le bon mot de passe."""
        from src.auth.service import AuthService

        auth = AuthService()
        password = "TestPassword123!"
        hashed = auth.get_password_hash(password)

        assert auth.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self, mock_settings):
        """Vérification échoue avec un mauvais mot de passe."""
        from src.auth.service import AuthService

        auth = AuthService()
        password = "TestPassword123!"
        wrong_password = "WrongPassword456!"
        hashed = auth.get_password_hash(password)

        assert auth.verify_password(wrong_password, hashed) is False


class TestAuthServiceTokens:
    """Tests pour la création de tokens JWT."""

    def test_create_access_token_returns_string(self, mock_settings):
        """create_access_token retourne un token string."""
        from src.auth.service import AuthService

        auth = AuthService()
        data = {"sub": "user-123", "username": "testuser"}
        token = auth.create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2  # JWT format: header.payload.signature

    def test_create_refresh_token_returns_string(self, mock_settings):
        """create_refresh_token retourne un token string."""
        from src.auth.service import AuthService

        auth = AuthService()
        data = {"sub": "user-123"}
        token = auth.create_refresh_token(data)

        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2

    def test_verify_token_valid_access_token(self, mock_settings):
        """verify_token décode un token valide."""
        from src.auth.service import AuthService

        auth = AuthService()
        data = {"sub": "user-123", "username": "testuser"}
        token = auth.create_access_token(data)
        payload = auth.verify_token(token, "access")

        assert payload["sub"] == "user-123"
        assert payload["username"] == "testuser"
        assert payload["type"] == "access"

    def test_verify_token_wrong_type_raises(self, mock_settings):
        """verify_token lève une exception si le type ne correspond pas."""
        from src.auth.service import AuthService
        from fastapi import HTTPException

        auth = AuthService()
        data = {"sub": "user-123"}
        access_token = auth.create_access_token(data)

        with pytest.raises(HTTPException) as exc_info:
            auth.verify_token(access_token, "refresh")

        assert exc_info.value.status_code == 401
