"""
Tests unitaires pour services/auth_service.py
"""

import pytest


class TestAuthServicePasswordHashing:
    """Tests pour le hachage de mots de passe."""

    def test_get_password_hash_returns_hash(self):
        """Le hash retourne est different du mot de passe original."""
        from auth.service import AuthService

        auth = AuthService()
        password = "TestPassword123!"  # noqa: S105
        hashed = auth.get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$argon2")

    def test_verify_password_correct(self):
        """Verification reussie avec le bon mot de passe."""
        from auth.service import AuthService

        auth = AuthService()
        password = "TestPassword123!"  # noqa: S105
        hashed = auth.get_password_hash(password)

        assert auth.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Verification echoue avec un mauvais mot de passe."""
        from auth.service import AuthService

        auth = AuthService()
        password = "TestPassword123!"  # noqa: S105
        wrong_password = "WrongPassword456!"  # noqa: S105
        hashed = auth.get_password_hash(password)

        assert auth.verify_password(wrong_password, hashed) is False


class TestAuthServiceTokens:
    """Tests pour la creation de tokens JWT."""

    def test_create_access_token_returns_string(self):
        """create_access_token retourne un token string."""
        from auth.service import AuthService

        auth = AuthService()
        data = {"sub": "user-123", "username": "testuser"}
        token = auth.create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2  # JWT format: header.payload.signature

    def test_create_refresh_token_returns_string(self):
        """create_refresh_token retourne un token string."""
        from auth.service import AuthService

        auth = AuthService()
        data = {"sub": "user-123"}
        token = auth.create_refresh_token(data)

        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count(".") == 2

    def test_verify_token_valid_access_token(self):
        """verify_token decode un token valide."""
        from auth.service import AuthService

        auth = AuthService()
        data = {"sub": "user-123", "username": "testuser"}
        token = auth.create_access_token(data)
        payload = auth.verify_token(token, "access")

        assert payload["sub"] == "user-123"
        assert payload["username"] == "testuser"
        assert payload["type"] == "access"

    def test_verify_token_wrong_type_raises(self):
        """verify_token leve une exception si le type ne correspond pas."""
        from auth.service import AuthService
        from fastapi import HTTPException

        auth = AuthService()
        data = {"sub": "user-123"}
        access_token = auth.create_access_token(data)

        with pytest.raises(HTTPException) as exc_info:
            auth.verify_token(access_token, "refresh")

        assert exc_info.value.status_code == 401
