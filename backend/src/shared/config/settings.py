"""
Global application settings for the Crypto Trading Bot.
Handles all configuration including database fallback to SQLite.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import validator
from pydantic.types import SecretStr
from pydantic_settings import BaseSettings

# Configure logging
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Global application settings with automatic database fallback.
    Falls back to SQLite if PostgreSQL is not available.
    """

    # Application settings
    APP_NAME: str = "Crypto Trading Bot"
    APP_VERSION: str = "1.0.0"
    API_VERSION: str = "v1"
    API_PREFIX: str = f"/api/{API_VERSION}"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # Security settings
    SECRET_KEY: SecretStr = "your-secret-key-change-this-in-production"  # noqa: S105
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Server settings
    HOST: str = "0.0.0.0"  # noqa: S104
    PORT: int = 8000
    RELOAD: bool = True

    # CORS settings
    CORS_ORIGINS: list[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    # Trusted hosts
    ALLOWED_HOSTS: list[str] = ["*"]

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds

    # Database settings - PostgreSQL (primary)
    POSTGRES_HOST: str | None = None
    POSTGRES_PORT: int | None = None
    POSTGRES_USER: str | None = None
    POSTGRES_PWD: str | None = None
    POSTGRES_DB: str | None = None
    POSTGRES_URL: str | None = None

    # Database settings - SQLite (fallback)
    SQLITE_DB_PATH: str = "db.sqlite3"  # SQLite file at backend root, Django style
    USE_SQLITE_FALLBACK: bool = True
    DATABASE_ECHO: bool = False  # SQLAlchemy echo mode for debugging

    # Computed database URL
    DATABASE_URL: str | None = None

    # MongoDB settings (optional)
    MONGODB_HOST: str = "localhost"
    MONGODB_PORT: int = 27017
    MONGODB_USER: str | None = None
    MONGODB_PWD: str | None = None
    MONGODB_DB: str = "crypto_market_data"
    MONGODB_URL: str | None = None
    USE_MONGODB: bool = False

    # MinIO settings (optional)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "miniouser"
    MINIO_SECRET_KEY: SecretStr = "miniopassword"  # noqa: S105
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "crypto-bot-data"
    USE_MINIO: bool = False

    # Redis settings (optional)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: SecretStr | None = None
    REDIS_DB: int = 0
    REDIS_URL: str | None = None
    USE_REDIS: bool = False

    # Binance API settings
    BINANCE_API_KEY: SecretStr | None = None
    BINANCE_API_SECRET: SecretStr | None = None
    BINANCE_TESTNET: bool = True
    BINANCE_TESTNET_API_KEY: SecretStr | None = None
    BINANCE_TESTNET_API_SECRET: SecretStr | None = None

    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str | None = "logs/crypto_bot.log"

    # Feature flags
    ENABLE_BACKGROUND_TASKS: bool = True
    ENABLE_WEBSOCKETS: bool = True
    ENABLE_METRICS: bool = True
    ENABLE_HEALTH_CHECKS: bool = True

    # Environment detection
    IS_DOCKER: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra env vars not defined in the model

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-detect Docker environment
        self.IS_DOCKER = self._is_running_in_docker()

        # Adjust defaults based on environment
        if self.IS_DOCKER:
            self._adjust_for_docker()

        # Ensure data directories exist
        self._ensure_directories()

    def _is_running_in_docker(self) -> bool:
        """Detect if running inside Docker container."""
        try:
            # Check for Docker-specific files
            if Path("/.dockerenv").exists():
                return True

            # Check cgroup information
            with open("/proc/1/cgroup") as f:
                return "docker" in f.read()
        except Exception:
            return False

    def _adjust_for_docker(self) -> None:
        """Adjust settings for Docker environment."""
        # Use service names instead of localhost
        if not self.POSTGRES_HOST:
            self.POSTGRES_HOST = "postgres"
            self.POSTGRES_PORT = 5432

        if self.MONGODB_HOST == "localhost":
            self.MONGODB_HOST = "mongo"

        if self.MINIO_ENDPOINT == "localhost:9000":
            self.MINIO_ENDPOINT = "minio:9000"

        if self.REDIS_HOST == "localhost":
            self.REDIS_HOST = "redis"

        # Use mapped ports for development
        if not self.IS_DOCKER and self.POSTGRES_PORT == 5432:
            self.POSTGRES_PORT = 5434  # Mapped port for local development

    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        # Create data directory for SQLite
        sqlite_dir = Path(self.SQLITE_DB_PATH).parent
        sqlite_dir.mkdir(parents=True, exist_ok=True)

        # Create logs directory if log file is specified
        if self.LOG_FILE:
            log_dir = Path(self.LOG_FILE).parent
            log_dir.mkdir(parents=True, exist_ok=True)

    @validator("DATABASE_URL", pre=False, always=True)
    def build_database_url(cls, v, values):
        """Build database URL with automatic fallback to SQLite."""
        if v:
            return v

        # Try to build PostgreSQL URL
        postgres_host = values.get("POSTGRES_HOST")
        postgres_port = values.get("POSTGRES_PORT", 5432)
        postgres_user = values.get("POSTGRES_USER")
        postgres_password = values.get("POSTGRES_PWD")
        postgres_db = values.get("POSTGRES_DB")
        postgres_url = values.get("POSTGRES_URL")

        # Use explicit PostgreSQL URL if provided
        if postgres_url:
            logger.info("Using explicit PostgreSQL URL")
            return postgres_url

        # Build PostgreSQL URL if all components are available
        if all([postgres_host, postgres_user, postgres_password, postgres_db]):
            url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
            logger.info(f"Using PostgreSQL: {postgres_user}@{postgres_host}:{postgres_port}/{postgres_db}")
            return url

        # Fallback to SQLite
        sqlite_path = values.get("SQLITE_DB_PATH", "data/crypto_bot.db")
        use_fallback = values.get("USE_SQLITE_FALLBACK", True)

        if use_fallback:
            # Convert to absolute path
            if not Path(sqlite_path).is_absolute():
                sqlite_path = Path.cwd() / sqlite_path

            url = f"sqlite:///{sqlite_path}"
            logger.warning("PostgreSQL not configured, falling back to SQLite")
            logger.info(f"Using SQLite: {sqlite_path}")
            return url

        raise ValueError("No database configuration provided and SQLite fallback is disabled")

    @validator("MONGODB_URL", pre=False, always=True)
    def build_mongodb_url(cls, v, values):
        """Build MongoDB URL if enabled."""
        if v or not values.get("USE_MONGODB", False):
            return v

        host = values.get("MONGODB_HOST", "localhost")
        port = values.get("MONGODB_PORT", 27017)
        user = values.get("MONGODB_USER")
        password = values.get("MONGODB_PWD")
        db = values.get("MONGODB_DB", "crypto_market_data")

        if user and password:
            return f"mongodb://{user}:{password}@{host}:{port}/{db}?authSource=admin"
        else:
            return f"mongodb://{host}:{port}/{db}"

    @validator("REDIS_URL", pre=False, always=True)
    def build_redis_url(cls, v, values):
        """Build Redis URL if enabled."""
        if v or not values.get("USE_REDIS", False):
            return v

        host = values.get("REDIS_HOST", "localhost")
        port = values.get("REDIS_PORT", 6379)
        password = values.get("REDIS_PASSWORD")
        db = values.get("REDIS_DB", 0)

        if password:
            return f"redis://:{password.get_secret_value()}@{host}:{port}/{db}"
        else:
            return f"redis://{host}:{port}/{db}"

    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return self.DATABASE_URL and self.DATABASE_URL.startswith("sqlite://")

    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL database."""
        return self.DATABASE_URL and self.DATABASE_URL.startswith("postgresql://")

    def get_database_config(self) -> dict[str, Any]:
        """Get database configuration for SQLAlchemy."""
        config = {
            "url": self.DATABASE_URL,
            "echo": self.DEBUG,
        }

        # Add PostgreSQL-specific settings
        if self.is_postgresql():
            config.update(
                {
                    "pool_size": 10,
                    "max_overflow": 20,
                    "pool_timeout": 30,
                    "pool_recycle": 3600,
                    "pool_pre_ping": True,
                }
            )

        # Add SQLite-specific settings
        elif self.is_sqlite():
            config.update(
                {
                    "pool_pre_ping": True,
                    "connect_args": {
                        "check_same_thread": False,
                        "timeout": 30,
                    },
                }
            )

        return config

    def get_cors_config(self) -> dict[str, Any]:
        """Get CORS configuration."""
        return {
            "allow_origins": self.CORS_ORIGINS,
            "allow_credentials": self.CORS_ALLOW_CREDENTIALS,
            "allow_methods": self.CORS_ALLOW_METHODS,
            "allow_headers": self.CORS_ALLOW_HEADERS,
        }

    def setup_logging(self) -> None:
        """Configure application logging."""
        logging.basicConfig(
            level=getattr(logging, self.LOG_LEVEL.upper()),
            format=self.LOG_FORMAT,
            handlers=[
                logging.StreamHandler(),
                *([logging.FileHandler(self.LOG_FILE)] if self.LOG_FILE else []),
            ],
        )

        # Set specific logger levels
        logging.getLogger("uvicorn").setLevel(logging.INFO)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO if self.DEBUG else logging.WARNING)

    def log_configuration(self) -> None:
        """Log current configuration (without sensitive data)."""
        logger.info("=== Crypto Trading Bot Configuration ===")
        logger.info(f"App: {self.APP_NAME} v{self.APP_VERSION}")
        logger.info(f"Environment: {self.ENVIRONMENT}")
        logger.info(f"Debug: {self.DEBUG}")
        logger.info(f"Docker: {self.IS_DOCKER}")
        logger.info(f"API: {self.API_PREFIX}")
        logger.info(f"Server: {self.HOST}:{self.PORT}")

        # Database info
        if self.is_sqlite():
            logger.info(f"Database: SQLite ({Path(self.DATABASE_URL.replace('sqlite:///', '')).name})")
        elif self.is_postgresql():
            # Mask the password in the URL for logging
            masked_url = self.DATABASE_URL
            if "@" in masked_url:
                parts = masked_url.split("@")
                if ":" in parts[0]:
                    user_pass = parts[0].split("://")[1]
                    if ":" in user_pass:
                        user = user_pass.split(":")[0]
                        masked_url = masked_url.replace(user_pass, f"{user}:***")
            logger.info(f"Database: PostgreSQL ({masked_url.split('@')[1] if '@' in masked_url else 'unknown'})")

        # Optional services
        logger.info(f"MongoDB: {'Enabled' if self.USE_MONGODB else 'Disabled'}")
        logger.info(f"MinIO: {'Enabled' if self.USE_MINIO else 'Disabled'}")
        logger.info(f"Redis: {'Enabled' if self.USE_REDIS else 'Disabled'}")

        # Features
        features = []
        if self.ENABLE_BACKGROUND_TASKS:
            features.append("Background Tasks")
        if self.ENABLE_WEBSOCKETS:
            features.append("WebSockets")
        if self.ENABLE_METRICS:
            features.append("Metrics")
        if self.ENABLE_HEALTH_CHECKS:
            features.append("Health Checks")

        logger.info(f"Features: {', '.join(features) if features else 'None'}")
        logger.info("=" * 50)


@lru_cache
def get_settings() -> Settings:
    """Get application settings with caching."""
    return Settings()


# Export settings instance
settings = get_settings()

# Configure logging on import
if __name__ != "__main__":
    settings.setup_logging()
    settings.log_configuration()
