"""
User domain models for the Crypto Trading Bot.
Contains User, UserSession, UserAccount, and UserSettings models.
"""

import strategy.models  # noqa: F401
import trading.models  # noqa: F401
from shared.config.security import decrypt_secret, encrypt_secret
from shared.models.base import BaseModel, register_model
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship


@register_model
class User(BaseModel):
    """
    User model - Core user information.
    """

    __tablename__ = "users"

    # Basic user information
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)

    # Authentication
    hashed_password = Column(String(255), nullable=False)

    # Status flags
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    last_active_at = Column(DateTime, nullable=True, index=True)

    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    accounts = relationship("UserAccount", back_populates="user", cascade="all, delete-orphan")
    settings = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Strategy relationships
    strategies = relationship("Strategy", back_populates="user", cascade="all, delete-orphan")
    strategy_deployments = relationship("StrategyDeployment", back_populates="user", cascade="all, delete-orphan")
    strategy_states = relationship("StrategyState", back_populates="user", cascade="all, delete-orphan")
    trading_sessions = relationship("TradingSession", back_populates="user", cascade="all, delete-orphan")
    backtest_results = relationship("BacktestResult", back_populates="user", cascade="all, delete-orphan")

    # Trading relationships
    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.username

    @property
    def display_name(self) -> str:
        """Get user's display name (full name or username)."""
        return self.full_name if (self.first_name or self.last_name) else self.username

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"


@register_model
class UserSession(BaseModel):
    """
    User session model - Authentication and session management.
    """

    __tablename__ = "user_sessions"

    # Foreign key to user
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Session information
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)

    # Session metadata
    ip_address = Column(String(45), nullable=True)  # Supports IPv6
    user_agent = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")

    def is_expired(self) -> bool:
        """Check if the session is expired."""
        from datetime import UTC, datetime

        return datetime.now(UTC) > self.expires_at

    def __repr__(self) -> str:
        return f"<UserSession(id={self.id}, user_id={self.user_id}, expires_at={self.expires_at})>"


@register_model
class UserAccount(BaseModel):
    """
    User account model - Multiple auth providers (OAuth, credentials).
    """

    __tablename__ = "user_accounts"

    # Foreign key to user
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Provider information
    provider = Column(String(50), nullable=False, default="credentials")
    provider_id = Column(String(100), nullable=True)
    account_id = Column(String(255), nullable=False, index=True)

    # OAuth tokens
    scope = Column(String(1024), nullable=True)
    access_token = Column(String(1024), nullable=True)
    refresh_token = Column(String(1024), nullable=True)
    access_token_expires_at = Column(DateTime, nullable=True)
    refresh_token_expires_at = Column(DateTime, nullable=True)

    # Credentials provider
    password = Column(String(255), nullable=True)

    # Relationships
    user = relationship("User", back_populates="accounts")

    # Constraints
    __table_args__ = (UniqueConstraint("user_id", "provider", "provider_id", name="uq_user_provider_provider_id"),)

    @property
    def is_oauth_provider(self) -> bool:
        """Check if this is an OAuth provider."""
        return self.provider != "credentials"

    @property
    def is_credentials_provider(self) -> bool:
        """Check if this is a credentials provider."""
        return self.provider == "credentials"

    def is_access_token_expired(self) -> bool:
        """Check if the access token is expired."""
        if not self.access_token_expires_at:
            return False
        from datetime import UTC, datetime

        return datetime.now(UTC) > self.access_token_expires_at

    def is_refresh_token_expired(self) -> bool:
        """Check if the refresh token is expired."""
        if not self.refresh_token_expires_at:
            return False
        from datetime import UTC, datetime

        return datetime.now(UTC) > self.refresh_token_expires_at

    def __repr__(self) -> str:
        return f"<UserAccount(id={self.id}, user_id={self.user_id}, provider={self.provider})>"


@register_model
class UserSettings(BaseModel):
    """
    User settings model - Preferences and configuration.
    """

    __tablename__ = "user_settings"

    # Foreign key to user (one-to-one relationship)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # UI preferences
    theme = Column(String(20), default="light", nullable=False)

    # Notification preferences (JSON field for flexibility)
    notification_preferences = Column(JSON, default={"email": True, "push": False}, nullable=False)

    # Trading preferences
    risk_profile = Column(String(20), default="moderate", nullable=False)

    # API keys (encrypted JSON field)
    api_keys = Column(JSON, nullable=True)

    # Relationships
    user = relationship("User", back_populates="settings")

    @property
    def email_notifications_enabled(self) -> bool:
        """Check if email notifications are enabled."""
        return self.notification_preferences.get("email", False)

    @property
    def push_notifications_enabled(self) -> bool:
        """Check if push notifications are enabled."""
        return self.notification_preferences.get("push", False)

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    def _decrypt_value(self, stored_value):
        if stored_value is None:
            return None
        if isinstance(stored_value, dict) and "ciphertext" in stored_value and "nonce" in stored_value:
            return decrypt_secret(stored_value["ciphertext"], stored_value["nonce"])
        return stored_value

    def _is_legacy_entry(self, key: str, entry: dict) -> bool:
        """True when this entry uses the old {exchange: {api_key, api_secret}} format."""
        return "exchange" not in entry

    # ---------------------------------------------------------------------------
    # Multi-credential API (new format)
    # ---------------------------------------------------------------------------

    def get_all_credentials(self) -> list[dict]:
        """Return all stored credentials (masked). Handles both old and new format."""
        if not self.api_keys:
            return []
        result = []
        for key_id, entry in self.api_keys.items():
            if not isinstance(entry, dict):
                continue
            if self._is_legacy_entry(key_id, entry):
                raw = self._decrypt_value(entry.get("api_key")) or ""
                result.append(
                    {
                        "id": f"legacy_{key_id}",
                        "exchange": key_id,
                        "label": key_id.capitalize(),
                        "api_key_masked": (raw[:4] + "****") if len(raw) > 4 else "****",
                        "created_at": None,
                        "is_primary": entry.get("is_primary", True),
                    }
                )
            else:
                raw = self._decrypt_value(entry.get("api_key")) or ""
                result.append(
                    {
                        "id": key_id,
                        "exchange": entry.get("exchange", "binance"),
                        "label": entry.get("label", "Clef"),
                        "api_key_masked": (raw[:4] + "****") if len(raw) > 4 else "****",
                        "created_at": entry.get("created_at"),
                        "is_primary": entry.get("is_primary", False),
                    }
                )
        return result

    def add_credential(self, label: str, exchange: str, api_key: str, api_secret: str) -> str:
        """Add a named API credential. Returns the new key_id (UUID).
        First credential for an exchange is automatically set as primary."""
        import uuid
        from datetime import UTC, datetime

        if not self.api_keys:
            self.api_keys = {}
        is_first = not self.has_credentials_for_exchange(exchange)
        key_id = str(uuid.uuid4())
        self.api_keys[key_id] = {
            "exchange": exchange,
            "label": label,
            "api_key": encrypt_secret(api_key),
            "api_secret": encrypt_secret(api_secret),
            "created_at": datetime.now(UTC).isoformat(),
            "is_primary": is_first,
        }
        return key_id

    def set_primary_credential(self, key_id: str) -> bool:
        """Mark key_id as primary for its exchange, unmark all others. Returns True if found."""
        if not self.api_keys:
            return False
        actual_key = key_id[7:] if key_id.startswith("legacy_") else key_id
        entry = self.api_keys.get(actual_key)
        if not entry or not isinstance(entry, dict):
            return False
        exchange = actual_key if self._is_legacy_entry(actual_key, entry) else entry.get("exchange")
        for kid, e in self.api_keys.items():
            if not isinstance(e, dict):
                continue
            e_exchange = kid if self._is_legacy_entry(kid, e) else e.get("exchange")
            if e_exchange == exchange:
                e["is_primary"] = kid == actual_key
        return True

    def remove_credential(self, key_id: str) -> bool:
        """Remove a credential by key_id. If it was primary, promote the next one."""
        if not self.api_keys:
            return False
        if key_id.startswith("legacy_"):
            exchange = key_id[7:]
            if exchange in self.api_keys:
                del self.api_keys[exchange]
                return True
        if key_id not in self.api_keys:
            return False
        entry = self.api_keys[key_id]
        was_primary = isinstance(entry, dict) and entry.get("is_primary", False)
        exchange = entry.get("exchange") if isinstance(entry, dict) else None
        del self.api_keys[key_id]
        if was_primary and exchange:
            for _, e in self.api_keys.items():
                if isinstance(e, dict) and e.get("exchange") == exchange:
                    e["is_primary"] = True
                    break
        return True

    def get_credential_by_id(self, key_id: str) -> dict | None:
        """Return decrypted credentials dict for a given key_id, or None."""
        if not self.api_keys:
            return None
        if key_id.startswith("legacy_"):
            exchange = key_id[7:]
            entry = self.api_keys.get(exchange)
            if entry and self._is_legacy_entry(exchange, entry):
                return {
                    "exchange": exchange,
                    "label": exchange.capitalize(),
                    "api_key": self._decrypt_value(entry.get("api_key")),
                    "api_secret": self._decrypt_value(entry.get("api_secret")),
                }
        entry = self.api_keys.get(key_id)
        if not entry:
            return None
        return {
            "exchange": entry.get("exchange"),
            "label": entry.get("label"),
            "api_key": self._decrypt_value(entry.get("api_key")),
            "api_secret": self._decrypt_value(entry.get("api_secret")),
        }

    def has_credentials_for_exchange(self, exchange: str) -> bool:
        """True when at least one credential exists for the given exchange."""
        return self.get_api_key(exchange) is not None

    # ---------------------------------------------------------------------------
    # Backward-compatible single-exchange helpers
    # ---------------------------------------------------------------------------

    def get_api_key(self, exchange: str) -> str | None:
        """Get API key for exchange — primary first, then first available."""
        if not self.api_keys:
            return None
        entry = self.api_keys.get(exchange)
        if entry and isinstance(entry, dict) and self._is_legacy_entry(exchange, entry):
            return self._decrypt_value(entry.get("api_key"))
        first = None
        for v in self.api_keys.values():
            if isinstance(v, dict) and v.get("exchange") == exchange:
                if v.get("is_primary"):
                    return self._decrypt_value(v.get("api_key"))
                if first is None:
                    first = v
        return self._decrypt_value(first.get("api_key")) if first else None

    def get_api_secret(self, exchange: str) -> str | None:
        """Get API secret for exchange — primary first, then first available."""
        if not self.api_keys:
            return None
        entry = self.api_keys.get(exchange)
        if entry and isinstance(entry, dict) and self._is_legacy_entry(exchange, entry):
            return self._decrypt_value(entry.get("api_secret"))
        first = None
        for v in self.api_keys.values():
            if isinstance(v, dict) and v.get("exchange") == exchange:
                if v.get("is_primary"):
                    return self._decrypt_value(v.get("api_secret"))
                if first is None:
                    first = v
        return self._decrypt_value(first.get("api_secret")) if first else None

    def set_api_credentials(self, exchange: str, api_key: str, api_secret: str) -> None:
        """Set credentials in legacy format (backward compat — used by existing settings update)."""
        if not self.api_keys:
            self.api_keys = {}
        self.api_keys[exchange] = {
            "api_key": encrypt_secret(api_key),
            "api_secret": encrypt_secret(api_secret),
        }

    def remove_api_credentials(self, exchange: str) -> None:
        """Remove legacy-format credentials for an exchange."""
        if self.api_keys and exchange in self.api_keys:
            del self.api_keys[exchange]

    def __repr__(self) -> str:
        return f"<UserSettings(id={self.id}, user_id={self.user_id}, theme={self.theme})>"
