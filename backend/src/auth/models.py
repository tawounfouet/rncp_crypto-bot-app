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

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    def _decrypt_value(self, stored_value):
        if stored_value is None:
            return None
        if isinstance(stored_value, dict) and "ciphertext" in stored_value and "nonce" in stored_value:
            return decrypt_secret(stored_value["ciphertext"], stored_value["nonce"])
        return stored_value

    @staticmethod
    def _is_legacy_entry(entry: dict) -> bool:
        """Ancien format (cles a plat, sans sous-cles live/sandbox)."""
        return "api_key" in entry

    def _find_exchange_entries(self, exchange: str) -> list[tuple[str, dict]]:
        """Toutes les entrees (key, entry) associees a un exchange, quel que soit le format stocke.

        Deux formes coexistent pour la retro-compatibilite :
        - format "exchange-keyed" : {exchange: {api_key, api_secret}} (plat) ou
          {exchange: {active_mode, live, sandbox}} (mode simule/reel) ;
        - format "multi-credential" : {key_id: {exchange, label, api_key, api_secret, is_primary}}.
        """
        if not self.api_keys:
            return []
        entries = []
        for key, value in self.api_keys.items():
            if not isinstance(value, dict):
                continue
            if value.get("exchange") == exchange:
                entries.append((key, value))
            elif "exchange" not in value and key == exchange:
                entries.append((key, value))
        return entries

    def _credential_entry(self, exchange: str, mode: str | None = None) -> dict | None:
        """Resout le dict {api_key, api_secret} chiffre pour un exchange+mode.

        L'entree primaire est preferee en format multi-credential. Retro-compatible
        avec l'ancien format a plat (traite comme mode "live").
        """
        entries = self._find_exchange_entries(exchange)
        if not entries:
            return None
        primary = next((entry for _, entry in entries if entry.get("is_primary")), None)
        entry = primary if primary is not None else entries[0][1]
        if self._is_legacy_entry(entry):
            return entry if (mode or DEFAULT_CREDENTIAL_MODE) == DEFAULT_CREDENTIAL_MODE else None
        resolved_mode = mode or entry.get("active_mode", DEFAULT_CREDENTIAL_MODE)
        return entry.get(resolved_mode)

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
        entries = self._find_exchange_entries(exchange)
        if not entries:
            return DEFAULT_CREDENTIAL_MODE
        primary = next((entry for _, entry in entries if entry.get("is_primary")), None)
        entry = primary if primary is not None else entries[0][1]
        if self._is_legacy_entry(entry):
            return DEFAULT_CREDENTIAL_MODE
        return entry.get("active_mode", DEFAULT_CREDENTIAL_MODE)

    def has_credentials(self, exchange: str, mode: str) -> bool:
        """Indique si un jeu de cles existe pour ce mode precis (pas juste l'exchange)."""
        return self._credential_entry(exchange, mode) is not None

    def has_credentials_for_exchange(self, exchange: str) -> bool:
        """True quand au moins une credential existe pour l'exchange."""
        return bool(self._find_exchange_entries(exchange))

    def exchange_credentials_detail(self) -> dict[str, dict]:
        """Detail par exchange configure : quels modes ont des cles + lequel est actif.

        Utilise par GET /users/me/settings pour piloter l'UI (liste de portefeuilles,
        selecteur de mode) sans exposer les cles elles-memes.
        """
        if not self.api_keys:
            return {}
        detail: dict[str, dict] = {}
        for key, entry in self.api_keys.items():
            if not isinstance(entry, dict):
                continue
            exchange = entry.get("exchange", key)
            current = detail.setdefault(
                exchange,
                {"live": False, "sandbox": False, "active_mode": DEFAULT_CREDENTIAL_MODE},
            )
            if self._is_legacy_entry(entry):
                current["live"] = True
                continue
            current["live"] = current["live"] or (DEFAULT_CREDENTIAL_MODE in entry)
            current["sandbox"] = current["sandbox"] or (SANDBOX_CREDENTIAL_MODE in entry)
            current["active_mode"] = entry.get("active_mode", DEFAULT_CREDENTIAL_MODE)
        return detail

    def set_api_credentials(
        self, exchange: str, api_key: str, api_secret: str, mode: str = DEFAULT_CREDENTIAL_MODE
    ) -> None:
        """Enregistre des cles chiffrees pour un exchange, sur le slot live ou sandbox.

        Le mode enregistre devient automatiquement le mode actif de l'exchange.
        """
        if not self.api_keys:
            self.api_keys = {}
        entries = self._find_exchange_entries(exchange)
        if entries:
            primary = next((entry for _, entry in entries if entry.get("is_primary")), None)
            entry = primary if primary is not None else entries[0][1]
            if self._is_legacy_entry(entry):
                live_slot = {"api_key": entry["api_key"], "api_secret": entry["api_secret"]}
                meta = {k: entry[k] for k in ("exchange", "label", "is_primary", "created_at") if k in entry}
                entry.clear()
                entry.update(meta)
                entry["live"] = live_slot
        else:
            entry = {}
            self.api_keys[exchange] = entry

        entry[mode] = {"api_key": encrypt_secret(api_key), "api_secret": encrypt_secret(api_secret)}
        entry["active_mode"] = mode
        if "exchange" not in entry:
            entry["exchange"] = exchange
            entry["label"] = exchange.capitalize()
        flag_modified(self, "api_keys")

    def set_active_mode(self, exchange: str, mode: str) -> None:
        """Bascule le mode actif sans toucher aux cles.

        Kraken (pas de cles sandbox distinctes) : autorise de basculer sur "sandbox" tant que
        "live" existe -- le comportement (validate=true) est gere a l'execution, pas ici.
        """
        entries = self._find_exchange_entries(exchange)
        if not entries:
            raise ValueError(f"Exchange {exchange} non configure")

        primary = next((entry for _, entry in entries if entry.get("is_primary")), None)
        entry = primary if primary is not None else entries[0][1]
        if self._is_legacy_entry(entry):
            entry = {DEFAULT_CREDENTIAL_MODE: entry}
            self.api_keys[entries[0][0]] = entry

        if DEFAULT_CREDENTIAL_MODE not in entry:
            raise ValueError(f"Aucune cle live configuree pour {exchange}")
        if mode == SANDBOX_CREDENTIAL_MODE and SANDBOX_CREDENTIAL_MODE not in entry:
            # Pas de cles sandbox dediees (ex: Kraken) : le mode existe quand meme, il pilotera
            # `validate=true` a l'execution plutot qu'un jeu de cles different.
            pass
        elif mode not in (DEFAULT_CREDENTIAL_MODE, SANDBOX_CREDENTIAL_MODE):
            raise ValueError(f"Mode inconnu: {mode}")

        entry["active_mode"] = mode
        flag_modified(self, "api_keys")

    def remove_api_credentials(self, exchange: str, mode: str | None = None) -> None:
        """Supprime les cles d'un exchange (mode precis, ou tout l'exchange si mode omis)."""
        if not self.api_keys:
            return
        entries = self._find_exchange_entries(exchange)
        if not entries:
            return

        if mode is None:
            for key, _ in entries:
                del self.api_keys[key]
            flag_modified(self, "api_keys")
            return

        for key, entry in entries:
            if self._is_legacy_entry(entry):
                if mode == DEFAULT_CREDENTIAL_MODE:
                    del self.api_keys[key]
                continue
            entry.pop(mode, None)
            if DEFAULT_CREDENTIAL_MODE not in entry and SANDBOX_CREDENTIAL_MODE not in entry:
                del self.api_keys[key]
            elif entry.get("active_mode") == mode:
                entry["active_mode"] = (
                    DEFAULT_CREDENTIAL_MODE if DEFAULT_CREDENTIAL_MODE in entry else SANDBOX_CREDENTIAL_MODE
                )
        flag_modified(self, "api_keys")

    # ---------------------------------------------------------------------------
    # Multi-credential API (credentials nominees)
    # ---------------------------------------------------------------------------

    def get_all_credentials(self) -> list[dict]:
        """Return all stored credentials (masked). Handles all legacy/new formats."""
        if not self.api_keys:
            return []
        result = []
        for key_id, entry in self.api_keys.items():
            if not isinstance(entry, dict):
                continue
            if self._is_legacy_entry(entry):
                exchange = entry.get("exchange", key_id)
                ident = key_id if entry.get("exchange") else f"legacy_{key_id}"
                raw = self._decrypt_value(entry.get("api_key")) or ""
                result.append(
                    {
                        "id": ident,
                        "exchange": exchange,
                        "label": entry.get("label", exchange.capitalize()),
                        "api_key_masked": (raw[:4] + "****") if len(raw) > 4 else "****",
                        "created_at": entry.get("created_at"),
                        "is_primary": entry.get("is_primary", True),
                    }
                )
            else:
                raw = self._decrypt_value(entry.get("live", {}).get("api_key")) or ""
                result.append(
                    {
                        "id": key_id,
                        "exchange": key_id,
                        "label": key_id.capitalize(),
                        "api_key_masked": (raw[:4] + "****") if len(raw) > 4 else "****",
                        "created_at": None,
                        "is_primary": True,
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
        is_first = not self._find_exchange_entries(exchange)
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
        exchange = entry.get("exchange", actual_key)
        for kid, e in self.api_keys.items():
            if not isinstance(e, dict):
                continue
            e_exchange = e.get("exchange", kid)
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
            if entry and self._is_legacy_entry(entry):
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

    def __repr__(self) -> str:
        return f"<UserSettings(id={self.id}, user_id={self.user_id}, theme={self.theme})>"
