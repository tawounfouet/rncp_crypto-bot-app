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

    def test_export_user_data_includes_trading_data(self, patch_db_session):
        """export_user_data inclut strategies, deployments, ordres, transactions, sessions et backtests."""
        import uuid
        from datetime import UTC, datetime, timedelta
        from decimal import Decimal

        from auth.schemas import UserCreate
        from auth.user_service import UserService
        from strategy.models import BacktestResult, Strategy, StrategyDeployment, TradingSession
        from trading.models import Order, Transaction

        service = UserService()
        created = service.create_user(UserCreate(
            email="export3@test.com",
            username="exportuser3",
            password="SecurePass123!",
        ))
        user_id = created.id

        now = datetime.now(UTC)
        strategy = Strategy(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name="Bot export",
            strategy_type="ml_lstm",
            parameters={"budget_usdc": 1000.0},
        )
        patch_db_session.add(strategy)
        patch_db_session.flush()

        deployment = StrategyDeployment(
            id=str(uuid.uuid4()),
            strategy_id=strategy.id,
            user_id=user_id,
            exchange="binance",
            symbol="BTCUSDC",
            timeframe="1h",
            amount=Decimal("100.0"),
            is_paper=True,
            status="active",
            start_time=now,
        )
        patch_db_session.add(deployment)
        patch_db_session.flush()

        patch_db_session.add(
            Order(
                id=str(uuid.uuid4()),
                deployment_id=deployment.id,
                user_id=user_id,
                exchange="binance",
                symbol="BTCUSDC",
                order_type="MARKET",
                side="BUY",
                quantity=Decimal("0.01"),
            )
        )
        patch_db_session.add(
            Transaction(
                id=str(uuid.uuid4()),
                user_id=user_id,
                exchange="binance",
                transaction_type="TRADE",
                asset="BTC",
                amount=Decimal("0.01"),
                direction="IN",
                timestamp=now,
            )
        )
        patch_db_session.add(
            TradingSession(
                id=str(uuid.uuid4()),
                deployment_id=deployment.id,
                user_id=user_id,
                start_time=now,
                initial_balance=Decimal("1000.0"),
                status="ACTIVE",
            )
        )
        patch_db_session.add(
            BacktestResult(
                id=str(uuid.uuid4()),
                strategy_id=strategy.id,
                user_id=user_id,
                symbol="BTCUSDC",
                timeframe="1h",
                start_date=now - timedelta(days=30),
                end_date=now,
                parameters={},
                results={},
                metrics={"total_return": 0.05},
            )
        )
        patch_db_session.flush()

        data = service.export_user_data(user_id)

        assert len(data["strategies"]) == 1
        assert data["strategies"][0]["name"] == "Bot export"
        assert len(data["strategy_deployments"]) == 1
        assert data["strategy_deployments"][0]["is_paper"] is True
        assert len(data["orders"]) == 1
        assert data["orders"][0]["side"] == "BUY"
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["asset"] == "BTC"
        assert len(data["trading_sessions"]) == 1
        assert data["trading_sessions"][0]["status"] == "ACTIVE"
        assert len(data["backtest_results"]) == 1
        assert data["backtest_results"][0]["metrics"]["total_return"] == 0.05


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

    def test_delete_user_removes_full_trading_tree(self, patch_db_session):
        """Supprimer un user purge tout l'arbre trading (strategie, deployment, ordres, etats).

        Meme chemin ORM (session.delete(user)) que la purge Airflow
        delete_inactive_users_older_than -- valide que la purge ne casse pas
        sur un user ayant des donnees de trading.
        """
        import uuid
        from datetime import UTC, datetime, timedelta
        from decimal import Decimal

        from auth.schemas import UserCreate
        from auth.user_service import UserService
        from strategy.models import (
            BacktestResult,
            Strategy,
            StrategyDeployment,
            StrategyState,
            TradingSession,
        )
        from trading.models import Order, OrderFill, Transaction

        service = UserService()
        created = service.create_user(UserCreate(
            email="cascade3@test.com",
            username="cascadeuser3",
            password="SecurePass123!",  # noqa: S106
        ))
        user_id = created.id

        now = datetime.now(UTC)
        strategy = Strategy(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name="Bot cascade",
            strategy_type="ml_lstm",
            parameters={"budget_usdc": 1000.0},
        )
        patch_db_session.add(strategy)
        patch_db_session.flush()

        deployment = StrategyDeployment(
            id=str(uuid.uuid4()),
            strategy_id=strategy.id,
            user_id=user_id,
            exchange="binance",
            symbol="BTCUSDC",
            timeframe="1h",
            amount=Decimal("100.0"),
            is_paper=True,
            status="active",
            start_time=now,
        )
        patch_db_session.add(deployment)
        patch_db_session.flush()

        patch_db_session.add(
            StrategyState(
                id=str(uuid.uuid4()),
                deployment_id=deployment.id,
                user_id=user_id,
                position="LONG",
                total_trades=3,
            )
        )

        order = Order(
            id=str(uuid.uuid4()),
            deployment_id=deployment.id,
            user_id=user_id,
            exchange="binance",
            symbol="BTCUSDC",
            order_type="MARKET",
            side="BUY",
            quantity=Decimal("0.01"),
        )
        patch_db_session.add(order)
        patch_db_session.flush()

        patch_db_session.add(
            OrderFill(
                id=str(uuid.uuid4()),
                order_id=order.id,
                trade_id="trade-1",
                price=Decimal("65000.0"),
                quantity=Decimal("0.01"),
                commission=Decimal("0.65"),
                commission_asset="USDC",
                timestamp=now,
            )
        )
        patch_db_session.add(
            Transaction(
                id=str(uuid.uuid4()),
                user_id=user_id,
                order_id=order.id,
                exchange="binance",
                transaction_type="TRADE",
                asset="BTC",
                amount=Decimal("0.01"),
                direction="IN",
                timestamp=now,
            )
        )
        patch_db_session.add(
            TradingSession(
                id=str(uuid.uuid4()),
                deployment_id=deployment.id,
                user_id=user_id,
                start_time=now,
                initial_balance=Decimal("1000.0"),
                status="ACTIVE",
            )
        )
        patch_db_session.add(
            BacktestResult(
                id=str(uuid.uuid4()),
                strategy_id=strategy.id,
                user_id=user_id,
                symbol="BTCUSDC",
                timeframe="1h",
                start_date=now - timedelta(days=30),
                end_date=now,
                parameters={},
                results={},
                metrics={"total_return": 0.05},
            )
        )
        patch_db_session.flush()

        service.delete_user(user_id)

        assert patch_db_session.query(Strategy).filter(Strategy.user_id == user_id).first() is None
        assert patch_db_session.query(StrategyDeployment).filter(
            StrategyDeployment.user_id == user_id
        ).first() is None
        assert patch_db_session.query(StrategyState).filter(StrategyState.user_id == user_id).first() is None
        assert patch_db_session.query(Order).filter(Order.user_id == user_id).first() is None
        assert patch_db_session.query(OrderFill).filter(
            OrderFill.order_id == order.id
        ).first() is None
        assert patch_db_session.query(Transaction).filter(Transaction.user_id == user_id).first() is None
        assert patch_db_session.query(TradingSession).filter(TradingSession.user_id == user_id).first() is None
        assert patch_db_session.query(BacktestResult).filter(BacktestResult.user_id == user_id).first() is None


class TestUserSettingsCredentialModes:
    """Tests d'integration pour le mode simule/reel (live/sandbox) des cles API."""

    def _create_user(self, email: str):
        from auth.schemas import UserCreate
        from auth.user_service import UserService

        service = UserService()
        user = service.create_user(UserCreate(
            email=email,
            username=email.split("@")[0],
            password="SecurePass123!",  # noqa: S106
        ))
        return service, user

    def test_set_live_and_sandbox_credentials_then_switch_active_mode(self, patch_db_session, monkeypatch):
        import base64
        import os

        monkeypatch.setenv("EXCHANGE_ENC_KEY", base64.b64encode(os.urandom(32)).decode())
        from auth.schemas import UserSettingsUpdate

        service, user = self._create_user("modes1@test.com")

        service.update_user_settings(
            user.id,
            UserSettingsUpdate(exchange="binance", api_key="live_key", api_secret="live_secret", mode="live"),
        )
        service.update_user_settings(
            user.id,
            UserSettingsUpdate(
                exchange="binance", api_key="sandbox_key", api_secret="sandbox_secret", mode="sandbox"
            ),
        )

        settings = service.get_user_settings(user.id)
        assert settings["exchange_credentials"]["binance"] == {
            "live": True,
            "sandbox": True,
            "active_mode": "sandbox",  # dernier mode enregistre = actif
        }

        result = service.update_user_settings(user.id, UserSettingsUpdate(exchange="binance", mode="live"))

        assert result["exchange_credentials"]["binance"]["active_mode"] == "live"

    def test_switch_active_mode_without_existing_credentials_raises_400(self, patch_db_session, monkeypatch):
        import base64
        import os

        monkeypatch.setenv("EXCHANGE_ENC_KEY", base64.b64encode(os.urandom(32)).decode())
        from fastapi import HTTPException

        from auth.schemas import UserSettingsUpdate

        service, user = self._create_user("modes2@test.com")

        with pytest.raises(HTTPException) as exc_info:
            service.update_user_settings(user.id, UserSettingsUpdate(exchange="binance", mode="live"))

        assert exc_info.value.status_code == 400

    def test_kraken_active_mode_switches_without_a_second_credential_set(self, patch_db_session, monkeypatch):
        import base64
        import os

        monkeypatch.setenv("EXCHANGE_ENC_KEY", base64.b64encode(os.urandom(32)).decode())
        from auth.schemas import UserSettingsUpdate

        service, user = self._create_user("modes3@test.com")

        service.update_user_settings(
            user.id,
            UserSettingsUpdate(exchange="kraken", api_key="real_key", api_secret="real_secret", mode="live"),
        )
        result = service.update_user_settings(user.id, UserSettingsUpdate(exchange="kraken", mode="sandbox"))

        assert result["exchange_credentials"]["kraken"] == {
            "live": True,
            "sandbox": False,  # jamais de cles sandbox pour Kraken, seul le mode actif change
            "active_mode": "sandbox",
        }
