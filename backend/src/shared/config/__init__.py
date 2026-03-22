"""
Configuration package for the crypto trading bot.

This package contains all application configuration including:
- Global settings and environment variables
- Security configuration and utilities
- Application constants and enums
- ASGI/WSGI configuration for deployment

For database configuration, see the database package.
"""

from .settings import Settings, get_settings
from .security import SecurityConfig
from .constants import (
    OrderSide,
    OrderType,
    OrderStatus,
    PositionSide,
    StrategyStatus,
    RiskLevel,
    AlertType,
    AlertStatus,
    UserRole,
    TransactionType,
    TransactionStatus,
)

# Core configuration exports only
__all__ = [
    # Settings
    "Settings",
    "get_settings",
    # Security
    "SecurityConfig",
    # Constants
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "PositionSide",
    "StrategyStatus",
    "RiskLevel",
    "AlertType",
    "AlertStatus",
    "UserRole",
    "TransactionType",
    "TransactionStatus",
]
