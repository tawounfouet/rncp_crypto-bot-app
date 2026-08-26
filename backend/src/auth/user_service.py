"""
User service for the Crypto Trading Bot application.
Handles user CRUD operations and business logic.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from shared.database.connection import get_db_session
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from auth.models import User, UserSettings
from auth.schemas import UserCreate, UserSettingsUpdate, UserUpdate
from auth.service import auth_service

# Constants
USER_NOT_FOUND = "User not found"


def _export_value(value: object) -> object:
    """Serialize scalar column values for a portable export (JSON-safe)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _model_to_dict(obj: object) -> dict:
    """Serialize a SQLAlchemy model to a plain dict (columns only, no relations)."""
    return {column.key: _export_value(getattr(obj, column.key)) for column in sa_inspect(obj).mapper.column_attrs}


class UserService:
    """Service for handling user operations."""

    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        with get_db_session() as session:
            # Check if user already exists
            existing_user = (
                session.query(User)
                .filter((User.email == user_data.email) | (User.username == user_data.username))
                .first()
            )

            if existing_user:
                if existing_user.email == user_data.email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already registered",
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Username already taken",
                    )

            # Create new user
            hashed_password = auth_service.get_password_hash(user_data.password)
            db_user = User(
                id=str(uuid.uuid4()),
                email=user_data.email,
                username=user_data.username,
                hashed_password=hashed_password,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                is_active=True,
                is_admin=False,
                last_active_at=datetime.now(UTC),
            )

            session.add(db_user)
            session.flush()  # Get the ID without committing

            # Create default settings for the user
            self.create_default_settings(db_user.id, session)

            # Force loading all attributes before session closes
            _ = db_user.id, db_user.email, db_user.username
            _ = db_user.first_name, db_user.last_name
            _ = db_user.is_active, db_user.is_admin
            _ = db_user.created_at, db_user.updated_at

            # Expunge the object from the session to make it independent
            session.expunge(db_user)

            return db_user

    def create_default_settings(self, user_id: str, session: Session):
        """Create default settings for a user."""
        default_settings = UserSettings(
            id=str(uuid.uuid4()),
            user_id=user_id,
            theme="light",
            notification_preferences={
                "email": True,
                "push": False,
                "trading_alerts": True,
                "price_alerts": True,
                "portfolio_alerts": True,
            },
            risk_profile="moderate",
            api_keys=None,
        )
        session.add(default_settings)

    def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if user is None:
                return None
            session.refresh(user)
            session.expunge(user)
            return user

    def get_user_by_username(self, username: str) -> User | None:
        """Get user by username."""
        with get_db_session() as session:
            return session.query(User).filter(User.username == username).first()

    def get_user_by_email(self, email: str) -> User | None:
        """Get user by email."""
        with get_db_session() as session:
            return session.query(User).filter(User.email == email).first()

    def update_user(self, user_id: str, user_data: UserUpdate) -> User:
        """Update user information."""
        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND)

            # Update user fields if provided
            update_data = user_data.model_dump(exclude_unset=True)

            # Check for username/email conflicts
            if "username" in update_data:
                existing_user = (
                    session.query(User).filter(User.username == update_data["username"], User.id != user_id).first()
                )
                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Username already taken",
                    )

            if "email" in update_data:
                existing_user = (
                    session.query(User).filter(User.email == update_data["email"], User.id != user_id).first()
                )
                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already registered",
                    )

            # Update user fields
            for field, value in update_data.items():
                if hasattr(user, field):
                    setattr(user, field, value)

            session.refresh(user)
            session.expunge(user)
            return user

    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND)

            session.delete(user)
            return True

    def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        is_active: bool | None = None,
        is_admin: bool | None = None,
    ) -> list[User]:
        """Get list of users with pagination and optional filters."""
        with get_db_session() as session:
            query = session.query(User)
            if search:
                like = f"%{search}%"
                query = query.filter((User.email.ilike(like)) | (User.username.ilike(like)))
            if is_active is not None:
                query = query.filter(User.is_active == is_active)
            if is_admin is not None:
                query = query.filter(User.is_admin == is_admin)
            users = query.offset(skip).limit(limit).all()
            for u in users:
                session.refresh(u)
                session.expunge(u)
            return users

    def get_user_settings(self, user_id: str) -> dict | None:
        """Get user settings as a plain dict to avoid DetachedInstanceError."""
        with get_db_session() as session:
            settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if settings is None:
                return None
            configured_exchanges = sorted(settings.exchange_credentials_detail())
            return {
                "theme": settings.theme,
                "risk_profile": settings.risk_profile,
                "notification_preferences": settings.notification_preferences,
                "configured_exchanges": configured_exchanges,
                "exchange_credentials": settings.exchange_credentials_detail(),
            }

    def export_user_data(self, user_id: str) -> dict:
        """Return the user's personal data for portability export."""
        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND)

            settings = user.settings
            settings_data = None
            if settings:
                settings_data = {
                    "theme": settings.theme,
                    "risk_profile": settings.risk_profile,
                    "notification_preferences": settings.notification_preferences,
                    "has_binance_credentials": settings.has_credentials_for_exchange("binance"),
                    "configured_exchanges": sorted(settings.exchange_credentials_detail()),
                    "exchange_credentials": settings.exchange_credentials_detail(),
                }

            accounts_data = [
                {
                    "provider": account.provider,
                    "provider_id": account.provider_id,
                    "account_id": account.account_id,
                    "is_oauth": account.is_oauth_provider,
                }
                for account in user.accounts
            ]

            # Trading data (relations du modele User) pour l'export RGPD complet
            strategies_data = [_model_to_dict(s) for s in user.strategies]
            deployments_data = [_model_to_dict(d) for d in user.strategy_deployments]
            orders_data = [_model_to_dict(o) for o in user.orders]
            transactions_data = [_model_to_dict(t) for t in user.transactions]
            sessions_data = [_model_to_dict(s) for s in user.trading_sessions]
            backtests_data = [_model_to_dict(b) for b in user.backtest_results]

            return {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                    "last_active_at": _export_value(user.last_active_at),
                    "created_at": _export_value(user.created_at),
                    "updated_at": _export_value(user.updated_at),
                },
                "settings": settings_data,
                "accounts": accounts_data,
                "strategies": strategies_data,
                "strategy_deployments": deployments_data,
                "orders": orders_data,
                "transactions": transactions_data,
                "trading_sessions": sessions_data,
                "backtest_results": backtests_data,
            }

    def delete_inactive_users_older_than(self, days: int = 730) -> int:
        """Delete users whose last_active_at is older than the configured threshold."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        with get_db_session() as session:
            users = session.query(User).filter(User.last_active_at.isnot(None), User.last_active_at < cutoff).all()
            deleted_count = 0
            for user in users:
                session.delete(user)
                deleted_count += 1
            return deleted_count

    def update_user_settings(self, user_id: str, settings_data: UserSettingsUpdate) -> dict:
        """Update user settings and return a plain dict to avoid DetachedInstanceError."""
        with get_db_session() as session:
            # Verify user exists
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND)

            # Get existing settings
            settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()

            if not settings:
                # Create new settings if none exist
                settings = UserSettings(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    theme="light",
                    notification_preferences={
                        "email": True,
                        "push": False,
                        "trading_alerts": True,
                        "price_alerts": True,
                        "portfolio_alerts": True,
                    },
                    risk_profile="moderate",
                    api_keys=None,
                )
                session.add(settings)

            # Update API credentials if provided (exchange defaults to "binance" for compat)
            update_data = settings_data.model_dump(exclude_unset=True)
            exchange = update_data.pop("exchange", None) or "binance"
            api_key = update_data.pop("api_key", None)
            api_secret = update_data.pop("api_secret", None)
            mode = update_data.pop("mode", None)

            try:
                if api_key is not None or api_secret is not None:
                    if api_key is None or api_secret is None:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Both api_key and api_secret are required together.",
                        )
                    if api_key == "" and api_secret == "":
                        settings.remove_api_credentials(exchange, mode=mode)
                    else:
                        settings.set_api_credentials(exchange, api_key, api_secret, mode=mode or "live")
                elif mode is not None:
                    # Pas de nouvelles cles : juste basculer le mode actif (deja configure).
                    settings.set_active_mode(exchange, mode)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

            # Update other settings fields if provided
            for field, value in update_data.items():
                if hasattr(settings, field):
                    setattr(settings, field, value)

            # Capture return values before session closes
            configured_exchanges = sorted(settings.exchange_credentials_detail())
            return {
                "theme": settings.theme,
                "risk_profile": settings.risk_profile,
                "notification_preferences": settings.notification_preferences,
                "configured_exchanges": configured_exchanges,
                "exchange_credentials": settings.exchange_credentials_detail(),
            }

    # ---------------------------------------------------------------------------
    # Multi-credential management
    # ---------------------------------------------------------------------------

    def _get_or_create_settings(self, session, user_id: str) -> UserSettings:
        settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if not settings:
            settings = UserSettings(
                id=str(uuid.uuid4()),
                user_id=user_id,
                theme="light",
                notification_preferences={"email": True, "push": False},
                risk_profile="moderate",
                api_keys=None,
            )
            session.add(settings)
        return settings

    def list_api_credentials(self, user_id: str) -> list[dict]:
        """List all API credentials for a user (masked)."""
        with get_db_session() as session:
            settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if not settings:
                return []
            return settings.get_all_credentials()

    def add_api_credential(self, user_id: str, label: str, exchange: str, api_key: str, api_secret: str) -> dict:
        """Add a named API credential. Returns the masked credential dict."""
        from sqlalchemy.orm.attributes import flag_modified

        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND)
            settings = self._get_or_create_settings(session, user_id)
            key_id = settings.add_credential(label, exchange, api_key, api_secret)
            flag_modified(settings, "api_keys")
            session.commit()
            raw = api_key
            return {
                "id": key_id,
                "exchange": exchange,
                "label": label,
                "api_key_masked": (raw[:4] + "****") if len(raw) > 4 else "****",
                "created_at": None,
            }

    def remove_api_credential(self, user_id: str, key_id: str) -> bool:
        """Remove an API credential by key_id. Returns True if removed."""
        from sqlalchemy.orm.attributes import flag_modified

        with get_db_session() as session:
            settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if not settings:
                return False
            removed = settings.remove_credential(key_id)
            if removed:
                flag_modified(settings, "api_keys")
                session.commit()
            return removed

    def set_primary_credential(self, user_id: str, key_id: str) -> bool:
        """Mark key_id as primary for its exchange. Returns True if found."""
        from sqlalchemy.orm.attributes import flag_modified

        with get_db_session() as session:
            settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if not settings:
                return False
            updated = settings.set_primary_credential(key_id)
            if updated:
                flag_modified(settings, "api_keys")
                session.commit()
            return updated

    # Admin operations
    def activate_user(self, user_id: str) -> bool:
        """Activate a user account (admin only)."""
        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND)

            user.is_active = True
            return True

    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account (admin only)."""
        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND)

            user.is_active = False
            return True

    def make_admin(self, user_id: str) -> bool:
        """Give admin privileges to a user (admin only)."""
        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND)

            user.is_admin = True
            return True

    def remove_admin(self, user_id: str) -> bool:
        """Remove admin privileges from a user (admin only)."""
        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND)

            user.is_admin = False
            return True


# Global user service instance
user_service = UserService()
