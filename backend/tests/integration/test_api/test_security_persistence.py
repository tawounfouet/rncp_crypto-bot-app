"""
Tests d'integration securite : ce qui atterrit reellement en base et dans les tokens.

Complementaire des tests unitaires existants (test_user_settings_encryption.py teste la
logique de chiffrement en memoire, sans jamais toucher une vraie base) : ici on persiste
dans une vraie base SQLite, on recharge dans une session fraiche, et on inspecte la
colonne brute -- exactement le genre de regression qu'un test unitaire sur l'objet Python
seul ne peut pas voir (ex: quelqu'un bypass set_api_credentials() et assigne api_keys
directement, ou une migration future stocke le champ en clair par erreur).

Perimetre : credentials exchange chiffrees au repos, mot de passe hashe (jamais en clair),
JWT signes/rejetes correctement, cascade de suppression complete (droit a l'oubli, cf.
issue crypto-bot#21).
"""

from __future__ import annotations

import base64
import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def encryption_key(monkeypatch):
    raw_key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("EXCHANGE_ENC_KEY", raw_key)
    return raw_key


@pytest.fixture
def session_factory(tmp_path, encryption_key):
    """Sa propre base SQLite fichier (pas la fixture partagee db_session/patch_db_session
    de conftest.py) : on veut ouvrir des sessions totalement fraiches pour etre surs de lire
    ce qui est reellement persiste, pas un objet Python garde en cache d'identite."""
    import auth.models  # noqa: F401 (enregistre aussi strategy/trading models, cf. imports du module)
    from shared.models.base import Base

    db_path = tmp_path / "security_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _make_user(session, user_id: str, hashed_password: str = "x") -> None:
    from auth.models import User

    session.add(
        User(
            id=user_id,
            email=f"{user_id}@test.dev",
            username=user_id,
            hashed_password=hashed_password,
            first_name="Test",
            last_name="User",
        )
    )
    session.commit()


class TestExchangeCredentialsEncryptedAtRest:
    """1. Les credentials exchange ne doivent jamais atterrir en clair en base."""

    def test_raw_db_column_never_contains_the_plaintext_secret(self, session_factory):
        from auth.models import UserSettings

        Session = session_factory
        _make_user(Session(), "user-creds")

        session1 = Session()
        creds = UserSettings(id="settings-creds", user_id="user-creds", theme="light", risk_profile="moderate")
        session1.add(creds)
        creds.set_api_credentials("binance", "PLAINTEXT_API_KEY", "PLAINTEXT_API_SECRET")
        session1.commit()
        session1.close()

        # Lecture brute de la colonne JSON, sans passer par decrypt_secret/get_api_key
        session2 = Session()
        raw_json = session2.execute(
            text("SELECT api_keys FROM user_settings WHERE user_id = :uid"), {"uid": "user-creds"}
        ).scalar_one()
        session2.close()

        assert "PLAINTEXT_API_KEY" not in raw_json
        assert "PLAINTEXT_API_SECRET" not in raw_json
        assert "ciphertext" in raw_json
        assert "nonce" in raw_json

    def test_decryption_still_works_after_reload_from_a_fresh_session(self, session_factory):
        from auth.models import UserSettings

        Session = session_factory
        _make_user(Session(), "user-creds-2")

        session1 = Session()
        creds = UserSettings(id="settings-creds-2", user_id="user-creds-2", theme="light", risk_profile="moderate")
        session1.add(creds)
        creds.set_api_credentials("kraken", "kraken_key", "kraken_secret")
        session1.commit()
        session1.close()

        session2 = Session()
        reloaded = session2.query(UserSettings).filter_by(user_id="user-creds-2").first()
        assert reloaded.get_api_key("kraken") == "kraken_key"
        assert reloaded.get_api_secret("kraken") == "kraken_secret"
        session2.close()


class TestPasswordNeverStoredInPlaintext:
    """2. Le mot de passe doit toujours etre hashe (argon2), jamais en clair."""

    def test_raw_db_column_never_contains_the_plaintext_password(self, session_factory):
        from auth.service import auth_service

        Session = session_factory
        plaintext_password = "SuperSecret123!"  # noqa: S105
        hashed = auth_service.get_password_hash(plaintext_password)

        session1 = Session()
        _make_user(session1, "user-pwd", hashed_password=hashed)

        session2 = Session()
        raw_hash = session2.execute(
            text("SELECT hashed_password FROM users WHERE id = :uid"), {"uid": "user-pwd"}
        ).scalar_one()
        session2.close()

        assert raw_hash != plaintext_password
        assert raw_hash.startswith("$argon2")

    def test_same_password_produces_different_hashes_for_two_users(self, session_factory):
        """Salt aleatoire : deux utilisateurs avec le meme mot de passe n'ont pas le meme hash
        (sinon une fuite de la base permettrait de reperer les mots de passe reutilises)."""
        from auth.service import auth_service

        Session = session_factory
        password = "SamePassword123!"  # noqa: S105
        hash1 = auth_service.get_password_hash(password)
        hash2 = auth_service.get_password_hash(password)

        session1 = Session()
        _make_user(session1, "user-a", hashed_password=hash1)
        session1.close()

        session2 = Session()
        _make_user(session2, "user-b", hashed_password=hash2)
        session2.close()

        assert hash1 != hash2
        # Les deux doivent quand meme se verifier correctement contre le mot de passe original
        assert auth_service.verify_password(password, hash1)
        assert auth_service.verify_password(password, hash2)


class TestJwtSigningAndRejection:
    """3. Les JWT emis par l'app sont valides ; ceux forges/expires sont rejetes."""

    def test_access_token_roundtrip(self):
        from auth.service import auth_service

        token = auth_service.create_access_token({"sub": "user-123"})
        payload = auth_service.verify_token(token, "access")

        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_token_signed_with_a_different_key_is_rejected(self):
        """Un token qui n'a pas ete signe avec JWT_SIGNING_KEY doit etre rejete (401),
        meme s'il a un payload/format parfaitement valide par ailleurs -- c'est exactement
        le scenario que corrige l'issue crypto-bot#72 (plus de cle par defaut publique)."""
        from fastapi import HTTPException

        from auth.service import auth_service

        forged_payload = {
            "sub": "attacker",
            "is_admin": True,
            "type": "access",
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        }
        forged_token = jwt.encode(forged_payload, "wrong-signing-key", algorithm=auth_service.algorithm)

        with pytest.raises(HTTPException) as exc_info:
            auth_service.verify_token(forged_token, "access")
        assert exc_info.value.status_code == 401

    def test_expired_token_is_rejected(self):
        from fastapi import HTTPException

        from auth.service import auth_service

        expired_payload = {
            "sub": "user-123",
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        }
        expired_token = jwt.encode(expired_payload, auth_service.secret_key, algorithm=auth_service.algorithm)

        with pytest.raises(HTTPException) as exc_info:
            auth_service.verify_token(expired_token, "access")
        assert exc_info.value.status_code == 401

    def test_refresh_token_rejected_as_access_token(self):
        """Un refresh token ne doit pas etre accepte a la place d'un access token."""
        from fastapi import HTTPException

        from auth.service import auth_service

        refresh_token = auth_service.create_refresh_token({"sub": "user-123"})

        with pytest.raises(HTTPException):
            auth_service.verify_token(refresh_token, "access")


class TestAccountDeletionCascade:
    """4. Le droit a l'oubli (DELETE /me) doit purger toutes les donnees liees, pas
    seulement la ligne 'users' (cf. issue crypto-bot#21, export/purge RGPD)."""

    def test_deleting_a_user_removes_settings_and_sessions(self, session_factory):
        from auth.models import User, UserSession, UserSettings

        Session = session_factory
        session1 = Session()
        _make_user(session1, "user-to-delete")
        session1.add(
            UserSettings(id="settings-to-delete", user_id="user-to-delete", theme="light", risk_profile="moderate")
        )
        session1.add(
            UserSession(
                id="session-to-delete",
                user_id="user-to-delete",
                token="refresh-token-value",  # noqa: S106
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        session1.commit()
        session1.close()

        # Suppression (meme mecanisme que UserService.delete_user : session.delete(user)
        # puis commit, en s'appuyant sur cascade="all, delete-orphan" des relationships)
        session2 = Session()
        user = session2.query(User).filter_by(id="user-to-delete").first()
        session2.delete(user)
        session2.commit()
        session2.close()

        # Verification depuis une session fraiche : plus rien ne doit subsister
        session3 = Session()
        assert session3.query(User).filter_by(id="user-to-delete").first() is None
        assert session3.query(UserSettings).filter_by(user_id="user-to-delete").first() is None
        assert session3.query(UserSession).filter_by(user_id="user-to-delete").first() is None
        session3.close()
