"""
Constants for the Crypto Trading Bot.
Centralized constants and enumerations.
"""

from enum import Enum


# Database constants
class DatabaseType(Enum):
    """Database types."""

    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


# User constants
class UserRole(Enum):
    """User roles."""

    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class UserStatus(Enum):
    """User status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"


# Trading constants
class OrderType(Enum):
    """Order types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    OCO = "oco"  # One-Cancels-Other


class OrderSide(Enum):
    """Order sides."""

    BUY = "buy"
    SELL = "sell"


class PositionSide(Enum):
    """Position sides for futures trading."""

    LONG = "long"
    SHORT = "short"
    BOTH = "both"  # For hedge mode


class OrderStatus(Enum):
    """Order status."""

    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TransactionType(Enum):
    """Transaction types."""

    BUY = "buy"
    SELL = "sell"
    FEE = "fee"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"


class TransactionDirection(Enum):
    """Transaction directions."""

    IN = "in"
    OUT = "out"


# Strategy constants
class StrategyType(Enum):
    """Strategy types."""

    SMA_CROSSOVER = "sma_crossover"
    RSI_OVERSOLD = "rsi_oversold"
    BOLLINGER_BANDS = "bollinger_bands"
    MACD = "macd"
    GRID_TRADING = "grid_trading"
    DCA = "dca"  # Dollar Cost Averaging
    CUSTOM = "custom"


class StrategyStatus(Enum):
    """Strategy status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class DeploymentStatus(Enum):
    """Strategy deployment status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    STARTING = "starting"
    STOPPING = "stopping"
    ERROR = "error"


# Market data constants
class TimeFrame(Enum):
    """Time frames for market data."""

    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
    EIGHT_HOURS = "8h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    THREE_DAYS = "3d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"


class Exchange(Enum):
    """Supported exchanges."""

    BINANCE = "binance"
    BINANCE_US = "binance_us"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    KUCOIN = "kucoin"


# Risk management constants
class RiskProfile(Enum):
    """Risk profiles."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class RiskLevel(Enum):
    """Risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Alert constants
class AlertType(Enum):
    """Alert types."""

    PRICE = "price"
    VOLUME = "volume"
    INDICATOR = "indicator"
    ORDER = "order"
    BALANCE = "balance"
    SYSTEM = "system"


class AlertStatus(Enum):
    """Alert status."""

    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    DISABLED = "disabled"


class TransactionStatus(Enum):
    """Transaction status."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Notification constants
class NotificationType(Enum):
    """Notification types."""

    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    WEBHOOK = "webhook"


class NotificationPriority(Enum):
    """Notification priorities."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# API constants
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"


# Error codes
class ErrorCode(Enum):
    """Error codes."""

    # Authentication errors
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"  # noqa: S105
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"

    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_FIELD = "MISSING_FIELD"

    # Database errors
    DATABASE_ERROR = "DATABASE_ERROR"
    NOT_FOUND = "NOT_FOUND"
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"

    # Trading errors
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    INVALID_ORDER = "INVALID_ORDER"
    EXCHANGE_ERROR = "EXCHANGE_ERROR"

    # Strategy errors
    STRATEGY_ERROR = "STRATEGY_ERROR"
    DEPLOYMENT_ERROR = "DEPLOYMENT_ERROR"

    # System errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


# Default configuration values
DEFAULT_CONFIG = {
    "database": {
        "sqlite_path": "data/crypto_bot.db",
        "use_sqlite_fallback": True,
        "pool_size": 10,
        "max_overflow": 20,
    },
    "security": {
        "algorithm": "HS256",
        "access_token_expire_minutes": 30,
        "refresh_token_expire_days": 7,
    },
    "api": {
        "version": API_VERSION,
        "prefix": API_PREFIX,
        "page_size": 20,
        "max_page_size": 100,
    },
    "trading": {
        "default_exchange": Exchange.BINANCE.value,
        "default_timeframe": TimeFrame.ONE_HOUR.value,
        "price_precision": 8,
        "quantity_precision": 8,
    },
    "features": {
        "enable_background_tasks": True,
        "enable_websockets": True,
        "enable_metrics": True,
        "enable_health_checks": True,
    },
}
