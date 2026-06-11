"""
User service for the Crypto Trading Bot application.
Handles user CRUD operations and business logic.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from shared.database.connection import get_db_session
from sqlalchemy.orm import Session

from auth.models import User, UserSettings
from auth.schemas import UserCreate, UserSettingsUpdate, UserUpdate
from auth.service import auth_service

# Constants
USER_NOT_FOUND = "User not found"


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
            has_binance = bool(settings.api_keys and "binance" in settings.api_keys)
            return {
                "theme": settings.theme,
                "risk_profile": settings.risk_profile,
                "notification_preferences": settings.notification_preferences,
                "has_binance_credentials": has_binance,
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
                    "has_binance_credentials": bool(settings.api_keys and "binance" in settings.api_keys),
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

            # Update API credentials if provided
            update_data = settings_data.model_dump(exclude_unset=True)
            binance_api_key = update_data.pop("binance_api_key", None)
            binance_api_secret = update_data.pop("binance_api_secret", None)

            if binance_api_key is not None or binance_api_secret is not None:
                if binance_api_key is None or binance_api_secret is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Both binance_api_key and binance_api_secret are required together.",
                    )
                if binance_api_key == "" and binance_api_secret == "":
                    settings.remove_api_credentials("binance")
                else:
                    settings.set_api_credentials("binance", binance_api_key, binance_api_secret)

            # Update other settings fields if provided
            for field, value in update_data.items():
                if hasattr(settings, field):
                    setattr(settings, field, value)

            # Capture return values before session closes
            has_binance = bool(settings.api_keys and "binance" in settings.api_keys)
            return {
                "theme": settings.theme,
                "risk_profile": settings.risk_profile,
                "notification_preferences": settings.notification_preferences,
                "has_binance_credentials": has_binance,
            }

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
