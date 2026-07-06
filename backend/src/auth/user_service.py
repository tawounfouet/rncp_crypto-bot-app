"""
User service for the Crypto Trading Bot application.
Handles user CRUD operations and business logic.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from shared.database.connection import get_db_session
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.models import User, UserExchangeCredential, UserSettings
from auth.schemas import (
    BinanceCredentialsStatus,
    ExchangeCredentialResponse,
    UserCreate,
    UserSettingsUpdate,
    UserUpdate,
)
from auth.service import auth_service

# Constants
USER_NOT_FOUND = "User not found"
BINANCE_EXCHANGE = "binance_spot_testnet"
LEGACY_BINANCE_EXCHANGE = "binance"


class UserService:
    """Service for handling user operations."""

    @staticmethod
    def _mask_secret(secret: str, visible: int = 4) -> str:
        if not secret:
            return ""
        if len(secret) <= visible * 2:
            return "*" * len(secret)
        return f"{secret[:visible]}{'*' * (len(secret) - visible * 2)}{secret[-visible:]}"

    def _settings_to_safe_dict(self, settings: UserSettings) -> dict:
        return {
            "theme": settings.theme,
            "risk_profile": settings.risk_profile,
            "notification_preferences": settings.notification_preferences,
            "has_binance_credentials": self._has_binance_credentials(settings),
        }

    @staticmethod
    def _has_binance_credentials(settings: UserSettings | None) -> bool:
        return bool(
            settings
            and settings.api_keys
            and (BINANCE_EXCHANGE in settings.api_keys or LEGACY_BINANCE_EXCHANGE in settings.api_keys)
        )

    @staticmethod
    def _active_exchange_credential(session: Session, user_id: str) -> UserExchangeCredential | None:
        return (
            session.query(UserExchangeCredential)
            .filter(
                UserExchangeCredential.user_id == user_id,
                UserExchangeCredential.exchange == "binance",
                UserExchangeCredential.environment == "testnet",
                UserExchangeCredential.is_active.is_(True),
            )
            .order_by(UserExchangeCredential.updated_at.desc())
            .first()
        )

    @staticmethod
    def _active_exchange_credential_by_id_or_alias(
        session: Session,
        user_id: str,
        credential_id: str,
    ) -> UserExchangeCredential | None:
        if credential_id in {BINANCE_EXCHANGE, LEGACY_BINANCE_EXCHANGE}:
            return UserService._active_exchange_credential(session, user_id)
        return (
            session.query(UserExchangeCredential)
            .filter(
                UserExchangeCredential.id == credential_id,
                UserExchangeCredential.user_id == user_id,
                UserExchangeCredential.is_active.is_(True),
            )
            .first()
        )

    def _credential_to_response(self, credential: UserExchangeCredential) -> ExchangeCredentialResponse:
        return ExchangeCredentialResponse(
            id=credential.id,
            exchange=credential.exchange,
            environment=credential.environment,
            configured=credential.is_active,
            updated_at=credential.updated_at,
            api_key_masked=self._mask_secret(credential.get_api_key() or ""),
            permissions_checked=credential.permissions_checked,
            last_verified_at=credential.last_verified_at,
        )

    def _create_settings(self, user_id: str, session: Session) -> UserSettings:
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
        session.flush()
        return settings

    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        email = str(user_data.email).strip().lower()
        username = user_data.username.strip()
        with get_db_session() as session:
            # Check if user already exists
            existing_user = (
                session.query(User).filter((func.lower(User.email) == email) | (User.username == username)).first()
            )

            if existing_user:
                if existing_user.email.lower() == email:
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
                email=email,
                username=username,
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
        self._create_settings(user_id, session)

    def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                self._prepare_user_response(session, user)
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
        """Get list of users with pagination."""
        with get_db_session() as session:
            query = session.query(User)
            if search:
                pattern = f"%{search}%"
                query = query.filter((User.username.ilike(pattern)) | (User.email.ilike(pattern)))
            if is_active is not None:
                query = query.filter(User.is_active == is_active)
            if is_admin is not None:
                query = query.filter(User.is_admin == is_admin)
            users = query.offset(skip).limit(limit).all()
            for user in users:
                self._prepare_user_response(session, user)
                session.expunge(user)
            return users

    def get_user_settings(self, user_id: str) -> dict | None:
        """Get user settings."""
        with get_db_session() as session:
            settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if not settings:
                return None
            return self._settings_to_safe_dict(settings)

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
                    "has_binance_credentials": self._has_binance_credentials(settings),
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

            return {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_active": user.is_active,
                    "is_admin": user.is_admin,
                    "last_active_at": user.last_active_at,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                },
                "settings": settings_data,
                "accounts": accounts_data,
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
        """Update user settings."""
        with get_db_session() as session:
            # Verify user exists
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND)

            # Get existing settings
            settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()

            if not settings:
                # Create new settings if none exist
                settings = self._create_settings(user_id, session)

            update_data = settings_data.model_dump(exclude_unset=True)

            # Update other settings fields if provided
            for field, value in update_data.items():
                if hasattr(settings, field):
                    setattr(settings, field, value)

            session.flush()
            return self._settings_to_safe_dict(settings)

    def get_binance_credentials_status(self, user_id: str) -> BinanceCredentialsStatus:
        """Return a safe Binance credentials status for the user."""
        with get_db_session() as session:
            credential = self._active_exchange_credential(session, user_id)
            if credential:
                return BinanceCredentialsStatus(
                    configured=True,
                    updated_at=credential.updated_at,
                    api_key_masked=self._mask_secret(credential.get_api_key() or ""),
                    permissions_checked=credential.permissions_checked,
                    last_verified_at=credential.last_verified_at,
                )

            settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if not self._has_binance_credentials(settings):
                return BinanceCredentialsStatus(configured=False)

            api_key = settings.get_api_key(BINANCE_EXCHANGE) or settings.get_api_key(LEGACY_BINANCE_EXCHANGE)
            return BinanceCredentialsStatus(
                configured=True,
                updated_at=settings.updated_at,
                api_key_masked=self._mask_secret(api_key or ""),
            )

    def save_binance_credentials(
        self,
        user_id: str,
        *,
        api_key: str,
        api_secret: str,
        password_confirmation: str,
    ) -> BinanceCredentialsStatus:
        """Validate and store Binance credentials encrypted for the user."""
        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND)

            if not auth_service.verify_password(password_confirmation, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid password confirmation",
                )

            settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if not settings:
                settings = self._create_settings(user_id, session)

            try:
                credential = self._active_exchange_credential(session, user_id)
                if not credential:
                    credential = UserExchangeCredential(
                        user_id=user_id,
                        exchange="binance",
                        environment="testnet",
                        label="Binance Spot Testnet principal",
                        is_active=True,
                        permissions_checked=False,
                    )
                    session.add(credential)
                credential.set_credentials(api_key, api_secret)
                credential.is_active = True
                credential.permissions_checked = False
                credential.last_verified_at = None
                credential.updated_at = datetime.now(UTC)
                settings.set_api_credentials(BINANCE_EXCHANGE, api_key, api_secret)
                settings.remove_api_credentials(LEGACY_BINANCE_EXCHANGE)
            except (RuntimeError, ValueError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Binance credential encryption is not configured correctly.",
                ) from exc

            settings.updated_at = datetime.now(UTC)
            session.flush()
            return BinanceCredentialsStatus(
                configured=True,
                updated_at=settings.updated_at,
                api_key_masked=self._mask_secret(api_key),
                permissions_checked=False,
                last_verified_at=None,
            )

    def delete_binance_credentials(self, user_id: str) -> BinanceCredentialsStatus:
        """Remove stored Binance credentials for the user."""
        with get_db_session() as session:
            credentials = (
                session.query(UserExchangeCredential)
                .filter(
                    UserExchangeCredential.user_id == user_id,
                    UserExchangeCredential.exchange == "binance",
                    UserExchangeCredential.environment == "testnet",
                    UserExchangeCredential.is_active.is_(True),
                )
                .all()
            )
            for credential in credentials:
                credential.is_active = False
                credential.updated_at = datetime.now(UTC)

            settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if settings:
                settings.remove_api_credentials(BINANCE_EXCHANGE)
                settings.remove_api_credentials(LEGACY_BINANCE_EXCHANGE)
                settings.updated_at = datetime.now(UTC)
                session.flush()
            return BinanceCredentialsStatus(configured=False)

    def list_exchange_credentials(self, user_id: str) -> list[ExchangeCredentialResponse]:
        """List active safe exchange credential descriptors for a user."""
        with get_db_session() as session:
            credentials = (
                session.query(UserExchangeCredential)
                .filter(
                    UserExchangeCredential.user_id == user_id,
                    UserExchangeCredential.is_active.is_(True),
                )
                .order_by(UserExchangeCredential.updated_at.desc())
                .all()
            )
            return [self._credential_to_response(credential) for credential in credentials]

    def get_exchange_credential(self, user_id: str, credential_id: str) -> UserExchangeCredential | None:
        """Return an active exchange credential owned by a user."""
        with get_db_session() as session:
            credential = self._active_exchange_credential_by_id_or_alias(session, user_id, credential_id)
            if credential:
                session.expunge(credential)
            return credential

    def verify_exchange_credential(
        self,
        user_id: str,
        credential_id: str,
        *,
        binance_service=None,
    ) -> ExchangeCredentialResponse:
        """Verify active Binance Spot Testnet credentials against Binance account permissions."""
        with get_db_session() as session:
            credential = self._active_exchange_credential_by_id_or_alias(session, user_id, credential_id)
            if not credential:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exchange credential not found")
            if credential.exchange != "binance" or credential.environment != "testnet":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only Binance Spot Testnet credentials can be verified.",
                )

        if binance_service is None:
            from market.binance_testnet_service import BinanceTestnetService

            binance_service = BinanceTestnetService()

        account_payload = binance_service.account(user_id)
        can_trade = bool(account_payload.get("canTrade"))
        verified_at = datetime.now(UTC)

        with get_db_session() as session:
            credential = self._active_exchange_credential_by_id_or_alias(session, user_id, credential_id)
            if not credential:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exchange credential not found")
            credential.permissions_checked = can_trade
            credential.last_verified_at = verified_at
            credential.updated_at = verified_at
            session.flush()
            response = self._credential_to_response(credential)

        if not can_trade:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Binance Testnet credentials are valid but trading permission is disabled.",
            )
        return response

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

    def _prepare_user_response(self, session: Session, user: User) -> None:
        """Load response fields and attach safe computed metadata before session close."""
        user.binance_configured = self._binance_configured_for_user(session, user.id)
        _ = user.id, user.email, user.username
        _ = user.first_name, user.last_name
        _ = user.is_active, user.is_admin
        _ = user.last_active_at, user.created_at, user.updated_at

    def _binance_configured_for_user(self, session: Session, user_id: str) -> bool:
        credential_exists = (
            session.query(UserExchangeCredential.id)
            .filter(
                UserExchangeCredential.user_id == user_id,
                UserExchangeCredential.exchange == "binance",
                UserExchangeCredential.environment == "testnet",
                UserExchangeCredential.is_active.is_(True),
            )
            .first()
            is not None
        )
        if credential_exists:
            return True
        settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        return self._has_binance_credentials(settings)


# Global user service instance
user_service = UserService()
