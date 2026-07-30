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
from sqlalchemy.orm.attributes import flag_modified

DEFAULT_CREDENTIAL_MODE = "live"
SANDBOX_CREDENTIAL_MODE = "sandbox"


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

    def _decrypt_value(self, stored_value):
        if stored_value is None:
            return None

        if isinstance(stored_value, dict) and "ciphertext" in stored_value and "nonce" in stored_value:
            return decrypt_secret(stored_value["ciphertext"], stored_value["nonce"])

        return stored_value

    @staticmethod
    def _is_legacy_entry(entry: dict) -> bool:
        """Ancien format (avant le mode simule/reel) : cles a plat, pas de sous-cles live/sandbox."""
        return "api_key" in entry

    def _credential_entry(self, exchange: str, mode: str | None = None) -> dict | None:
        """Resout le dict {api_key, api_secret} chiffre pour un exchange+mode.

        Retro-compatible avec l'ancien format a plat (traite comme mode "live").
        """
        if not self.api_keys or exchange not in self.api_keys:
            return None
        raw = self.api_keys[exchange]
        if self._is_legacy_entry(raw):
            return raw if (mode or DEFAULT_CREDENTIAL_MODE) == DEFAULT_CREDENTIAL_MODE else None
        resolved_mode = mode or raw.get("active_mode", DEFAULT_CREDENTIAL_MODE)
        return raw.get(resolved_mode)

    def get_api_key(self, exchange: str, mode: str | None = None) -> str | None:
        """Get API key for a specific exchange (mode actif si non precise)."""
        entry = self._credential_entry(exchange, mode)
        return self._decrypt_value(entry.get("api_key")) if entry else None

    def get_api_secret(self, exchange: str, mode: str | None = None) -> str | None:
        """Get API secret for a specific exchange (mode actif si non precise)."""
        entry = self._credential_entry(exchange, mode)
        return self._decrypt_value(entry.get("api_secret")) if entry else None

    def get_active_mode(self, exchange: str) -> str:
        """Mode actif ("live"/"sandbox") pour un exchange, "live" par defaut ou si non configure."""
        if not self.api_keys or exchange not in self.api_keys:
            return DEFAULT_CREDENTIAL_MODE
        raw = self.api_keys[exchange]
        if self._is_legacy_entry(raw):
            return DEFAULT_CREDENTIAL_MODE
        return raw.get("active_mode", DEFAULT_CREDENTIAL_MODE)

    def has_credentials(self, exchange: str, mode: str) -> bool:
        """Indique si un jeu de cles existe pour ce mode precis (pas juste l'exchange)."""
        return self._credential_entry(exchange, mode) is not None

    def exchange_credentials_detail(self) -> dict[str, dict]:
        """Detail par exchange configure : quels modes ont des cles + lequel est actif.

        Utilise par GET /users/me/settings pour piloter l'UI (liste de portefeuilles,
        selecteur de mode) sans exposer les cles elles-memes.
        """
        if not self.api_keys:
            return {}
        detail: dict[str, dict] = {}
        for exchange, entry in self.api_keys.items():
            if self._is_legacy_entry(entry):
                detail[exchange] = {"live": True, "sandbox": False, "active_mode": DEFAULT_CREDENTIAL_MODE}
                continue
            detail[exchange] = {
                "live": DEFAULT_CREDENTIAL_MODE in entry,
                "sandbox": SANDBOX_CREDENTIAL_MODE in entry,
                "active_mode": entry.get("active_mode", DEFAULT_CREDENTIAL_MODE),
            }
        return detail

    def set_api_credentials(
        self, exchange: str, api_key: str, api_secret: str, mode: str = DEFAULT_CREDENTIAL_MODE
    ) -> None:
        """Enregistre des cles chiffrees pour un exchange, sur le slot live ou sandbox.

        Le mode enregistre devient automatiquement le mode actif de l'exchange.
        """
        if not self.api_keys:
            self.api_keys = {}

        entry = self.api_keys.get(exchange)
        if not entry or self._is_legacy_entry(entry):
            entry = {}

        entry[mode] = {
            "api_key": encrypt_secret(api_key),
            "api_secret": encrypt_secret(api_secret),
        }
        entry["active_mode"] = mode
        self.api_keys[exchange] = entry
        flag_modified(self, "api_keys")  # mutation JSON en place non detectee sinon (cf. issue persistance)

    def set_active_mode(self, exchange: str, mode: str) -> None:
        """Bascule le mode actif sans toucher aux cles.

        Kraken (pas de cles sandbox distinctes) : autorise de basculer sur "sandbox" tant que
        "live" existe -- le comportement (validate=true) est gere a l'execution, pas ici.
        """
        if not self.api_keys or exchange not in self.api_keys:
            raise ValueError(f"Exchange {exchange} non configure")

        entry = self.api_keys[exchange]
        if self._is_legacy_entry(entry):
            entry = {DEFAULT_CREDENTIAL_MODE: entry}

        if DEFAULT_CREDENTIAL_MODE not in entry:
            raise ValueError(f"Aucune cle live configuree pour {exchange}")
        if mode == SANDBOX_CREDENTIAL_MODE and SANDBOX_CREDENTIAL_MODE not in entry:
            # Pas de cles sandbox dediees (ex: Kraken) : le mode existe quand meme, il pilotera
            # `validate=true` a l'execution plutot qu'un jeu de cles different.
            pass
        elif mode not in (DEFAULT_CREDENTIAL_MODE, SANDBOX_CREDENTIAL_MODE):
            raise ValueError(f"Mode inconnu: {mode}")

        entry["active_mode"] = mode
        self.api_keys[exchange] = entry
        flag_modified(self, "api_keys")

    def remove_api_credentials(self, exchange: str, mode: str | None = None) -> None:
        """Supprime les cles d'un exchange (mode precis, ou tout l'exchange si mode omis)."""
        if not self.api_keys or exchange not in self.api_keys:
            return

        if mode is None:
            del self.api_keys[exchange]
            flag_modified(self, "api_keys")
            return

        entry = self.api_keys[exchange]
        if self._is_legacy_entry(entry):
            if mode == DEFAULT_CREDENTIAL_MODE:
                del self.api_keys[exchange]
                flag_modified(self, "api_keys")
            return

        entry.pop(mode, None)
        if DEFAULT_CREDENTIAL_MODE not in entry and SANDBOX_CREDENTIAL_MODE not in entry:
            del self.api_keys[exchange]
        elif entry.get("active_mode") == mode:
            entry["active_mode"] = (
                DEFAULT_CREDENTIAL_MODE if DEFAULT_CREDENTIAL_MODE in entry else SANDBOX_CREDENTIAL_MODE
            )
            self.api_keys[exchange] = entry
        flag_modified(self, "api_keys")

    def __repr__(self) -> str:
        return f"<UserSettings(id={self.id}, user_id={self.user_id}, theme={self.theme})>"
