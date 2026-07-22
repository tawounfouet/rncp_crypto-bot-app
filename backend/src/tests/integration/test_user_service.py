"""
Tests d'integration pour le service utilisateur.
Utilise une vraie base SQLite en memoire pour valider le CRUD complet
et la persistance en BDD.

Les fixtures db_session, mock_settings et patch_db_session viennent de conftest.py.
"""

import pytest


class TestUserCreation:
    """Tests de creation d'utilisateur avec verification BDD."""

    def test_create_user_persisted_in_db(self, patch_db_session):
        """Un utilisateur cree est bien persiste en base."""
        from auth.models import User
        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()
        user_data = UserCreate(
            email="test@example.com",
            username="testuser",
            password="SecurePass123!",  # noqa: S106
            first_name="Test",
            last_name="User",
        )

        created_user = service.create_user(user_data)

        assert created_user.email == "test@example.com"
        assert created_user.username == "testuser"
        assert created_user.first_name == "Test"
        assert created_user.last_name == "User"
        assert created_user.is_active is True
        assert created_user.is_admin is False

        # Verifier en BDD
        db_user = patch_db_session.query(User).filter(User.username == "testuser").first()
        assert db_user is not None
        assert db_user.email == "test@example.com"
        assert db_user.hashed_password != "SecurePass123!"
        assert db_user.hashed_password.startswith("$argon2")

    def test_create_user_generates_uuid(self, patch_db_session):
        """L'ID genere est un UUID valide."""
        import uuid

        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()
        user_data = UserCreate(
            email="uuid@test.com",
            username="uuiduser",
            password="SecurePass123!",  # noqa: S106
        )

        created_user = service.create_user(user_data)
        uuid.UUID(created_user.id)

    def test_create_user_default_settings(self, patch_db_session):
        """La creation d'un utilisateur cree aussi ses settings par defaut."""
        from auth.models import UserSettings
        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()
        user_data = UserCreate(
            email="settings@test.com",
            username="settingsuser",
            password="SecurePass123!",  # noqa: S106
        )

        created_user = service.create_user(user_data)

        settings = patch_db_session.query(UserSettings).filter(
            UserSettings.user_id == created_user.id
        ).first()
        assert settings is not None
        assert settings.theme == "light"
        assert settings.risk_profile == "moderate"

    def test_create_duplicate_email_raises(self, patch_db_session):
        """La creation avec un email deja utilise leve une erreur."""
        from fastapi import HTTPException

        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()

        service.create_user(UserCreate(
            email="dup@test.com",
            username="user1",
            password="SecurePass123!",  # noqa: S106
        ))

        with pytest.raises(HTTPException) as exc_info:
            service.create_user(UserCreate(
                email="dup@test.com",
                username="user2",
                password="SecurePass123!",  # noqa: S106
            ))

        assert exc_info.value.status_code == 400
        assert "Email already registered" in str(exc_info.value.detail)

    def test_create_duplicate_username_raises(self, patch_db_session):
        """La creation avec un username deja utilise leve une erreur."""
        from fastapi import HTTPException

        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()

        service.create_user(UserCreate(
            email="first@test.com",
            username="dupuser",
            password="SecurePass123!",  # noqa: S106
        ))

        with pytest.raises(HTTPException) as exc_info:
            service.create_user(UserCreate(
                email="second@test.com",
                username="dupuser",
                password="SecurePass123!",  # noqa: S106
            ))

        assert exc_info.value.status_code == 400
        assert "Username already taken" in str(exc_info.value.detail)


class TestUserRetrieval:
    """Tests de lecture d'utilisateur en BDD."""

    def _create_test_user(self):
        """Helper pour creer un user de test."""
        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()
        return service.create_user(UserCreate(
            email="retrieve@test.com",
            username="retrieveuser",
            password="SecurePass123!",  # noqa: S106
            first_name="Retrieve",
            last_name="User",
        )), service

    def test_get_user_by_id(self, patch_db_session):
        """Retrouver un utilisateur par son ID."""
        created, service = self._create_test_user()
        found = service.get_user_by_id(created.id)

        assert found is not None
        assert found.id == created.id
        assert found.email == "retrieve@test.com"

    def test_get_user_by_username(self, patch_db_session):
        """Retrouver un utilisateur par son username."""
        created, service = self._create_test_user()
        found = service.get_user_by_username("retrieveuser")

        assert found is not None
        assert found.username == "retrieveuser"

    def test_get_user_by_email(self, patch_db_session):
        """Retrouver un utilisateur par son email."""
        created, service = self._create_test_user()
        found = service.get_user_by_email("retrieve@test.com")

        assert found is not None
        assert found.email == "retrieve@test.com"

    def test_get_nonexistent_user_returns_none(self, patch_db_session):
        """Chercher un user inexistant retourne None."""
        from auth.user_service import UserService

        service = UserService()
        assert service.get_user_by_id("nonexistent-id") is None
        assert service.get_user_by_username("ghost") is None
        assert service.get_user_by_email("ghost@test.com") is None


class TestUserDeletion:
    """Tests de suppression d'utilisateur."""

    def test_delete_user_removes_from_db(self, patch_db_session):
        """La suppression retire l'utilisateur de la BDD."""
        from auth.models import User
        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()
        created = service.create_user(UserCreate(
            email="delete@test.com",
            username="deleteuser",
            password="SecurePass123!",  # noqa: S106
        ))

        result = service.delete_user(created.id)
        assert result is True

        db_user = patch_db_session.query(User).filter(User.id == created.id).first()
        assert db_user is None

    def test_delete_nonexistent_user_raises(self, patch_db_session):
        """Supprimer un user inexistant leve une erreur 404."""
        from fastapi import HTTPException

        from auth.user_service import UserService

        service = UserService()
        with pytest.raises(HTTPException) as exc_info:
            service.delete_user("nonexistent-id")

        assert exc_info.value.status_code == 404


class TestUserAdminOperations:
    """Tests des operations admin."""

    def _create_test_user(self):
        """Helper pour creer un user de test."""
        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()
        return service.create_user(UserCreate(
            email="admin@test.com",
            username="adminuser",
            password="SecurePass123!",  # noqa: S106
        )), service

    def test_deactivate_user(self, patch_db_session):
        """Desactiver un utilisateur met is_active a False en BDD."""
        from auth.models import User

        created, service = self._create_test_user()
        service.deactivate_user(created.id)

        db_user = patch_db_session.query(User).filter(User.id == created.id).first()
        assert db_user.is_active is False

    def test_activate_user(self, patch_db_session):
        """Reactiver un utilisateur met is_active a True en BDD."""
        from auth.models import User

        created, service = self._create_test_user()
        service.deactivate_user(created.id)
        service.activate_user(created.id)

        db_user = patch_db_session.query(User).filter(User.id == created.id).first()
        assert db_user.is_active is True

    def test_make_admin(self, patch_db_session):
        """Promouvoir un utilisateur en admin met is_admin a True en BDD."""
        from auth.models import User

        created, service = self._create_test_user()
        service.make_admin(created.id)

        db_user = patch_db_session.query(User).filter(User.id == created.id).first()
        assert db_user.is_admin is True

    def test_remove_admin(self, patch_db_session):
        """Retirer le role admin met is_admin a False en BDD."""
        from auth.models import User

        created, service = self._create_test_user()
        service.make_admin(created.id)
        service.remove_admin(created.id)

        db_user = patch_db_session.query(User).filter(User.id == created.id).first()
        assert db_user.is_admin is False


class TestUserExportData:
    """Tests pour l'export des donnees utilisateur."""

    def test_export_user_data_structure(self, patch_db_session):
        """export_user_data retourne un dict avec les cles user, settings, accounts."""
        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()
        created = service.create_user(UserCreate(
            email="export@test.com",
            username="exportuser",
            password="SecurePass123!",  # noqa: S106
            first_name="Export",
            last_name="User",
        ))

        data = service.export_user_data(created.id)

        assert "user" in data
        assert "settings" in data
        assert "accounts" in data
        assert data["user"]["email"] == "export@test.com"
        assert data["user"]["username"] == "exportuser"
        assert data["user"]["first_name"] == "Export"
        assert data["user"]["last_name"] == "User"

    def test_export_user_data_includes_settings(self, patch_db_session):
        """export_user_data inclut les settings par defaut."""
        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()
        created = service.create_user(UserCreate(
            email="export2@test.com",
            username="exportuser2",
            password="SecurePass123!",  # noqa: S106
        ))

        data = service.export_user_data(created.id)

        assert data["settings"] is not None
        assert data["settings"]["theme"] == "light"
        assert data["settings"]["risk_profile"] == "moderate"
        assert data["settings"]["configured_exchanges"] == []

    def test_export_nonexistent_user_raises(self, patch_db_session):
        """export_user_data leve 404 pour un user inexistant."""
        from fastapi import HTTPException

        from auth.user_service import UserService

        service = UserService()
        with pytest.raises(HTTPException) as exc_info:
            service.export_user_data("nonexistent-id")

        assert exc_info.value.status_code == 404


class TestDeleteInactiveUsers:
    """Tests pour la suppression des utilisateurs inactifs."""

    def test_delete_inactive_users_removes_old_users(self, patch_db_session):
        """Les utilisateurs inactifs depuis plus de N jours sont supprimes."""
        from datetime import UTC, datetime, timedelta

        from auth.models import User
        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()

        # Creer un user actif recemment
        active = service.create_user(UserCreate(
            email="active@test.com",
            username="activeuser",
            password="SecurePass123!",  # noqa: S106
        ))

        # Creer un user inactif depuis 3 ans
        old = service.create_user(UserCreate(
            email="old@test.com",
            username="olduser",
            password="SecurePass123!",  # noqa: S106
        ))
        db_old = patch_db_session.query(User).filter(User.id == old.id).first()
        db_old.last_active_at = datetime.now(UTC) - timedelta(days=1100)
        patch_db_session.flush()

        deleted = service.delete_inactive_users_older_than(days=730)

        assert deleted == 1
        assert patch_db_session.query(User).filter(User.id == old.id).first() is None
        assert patch_db_session.query(User).filter(User.id == active.id).first() is not None

    def test_delete_inactive_users_skips_null_last_active(self, patch_db_session):
        """Les utilisateurs sans last_active_at ne sont pas supprimes."""
        from auth.models import User
        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()
        created = service.create_user(UserCreate(
            email="null@test.com",
            username="nulluser",
            password="SecurePass123!",  # noqa: S106
        ))

        # Mettre last_active_at a None
        db_user = patch_db_session.query(User).filter(User.id == created.id).first()
        db_user.last_active_at = None
        patch_db_session.flush()

        deleted = service.delete_inactive_users_older_than(days=1)

        assert deleted == 0
        assert patch_db_session.query(User).filter(User.id == created.id).first() is not None


class TestCascadeDelete:
    """Tests pour le comportement CASCADE a la suppression d'un utilisateur."""

    def test_delete_user_removes_settings(self, patch_db_session):
        """Supprimer un user supprime aussi ses settings en cascade."""
        from auth.models import User, UserSettings
        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()
        created = service.create_user(UserCreate(
            email="cascade@test.com",
            username="cascadeuser",
            password="SecurePass123!",  # noqa: S106
        ))

        # Verifier que les settings existent
        settings = patch_db_session.query(UserSettings).filter(
            UserSettings.user_id == created.id
        ).first()
        assert settings is not None

        # Supprimer le user
        service.delete_user(created.id)

        # Verifier que les settings sont supprimees
        settings = patch_db_session.query(UserSettings).filter(
            UserSettings.user_id == created.id
        ).first()
        assert settings is None

    def test_delete_user_removes_sessions(self, patch_db_session):
        """Supprimer un user supprime aussi ses sessions en cascade."""
        import uuid
        from datetime import UTC, datetime, timedelta

        from auth.models import User, UserSession
        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()
        created = service.create_user(UserCreate(
            email="cascade2@test.com",
            username="cascadeuser2",
            password="SecurePass123!",  # noqa: S106
        ))

        # Creer une session manuellement
        session_obj = UserSession(
            id=str(uuid.uuid4()),
            user_id=created.id,
            token="test-session-token",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        patch_db_session.add(session_obj)
        patch_db_session.flush()

        # Supprimer le user
        service.delete_user(created.id)

        # Verifier que la session est supprimee
        sessions = patch_db_session.query(UserSession).filter(
            UserSession.user_id == created.id
        ).all()
        assert len(sessions) == 0
