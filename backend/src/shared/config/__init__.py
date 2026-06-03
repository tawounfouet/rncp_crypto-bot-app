"""
Configuration package for the crypto trading bot.

This package contains all application configuration including:
- Global settings and environment variables
- Security configuration and utilities
- Application constants and enums
- ASGI/WSGI configuration for deployment

For database configuration, see the database package.
"""

from .constants import (
    AlertStatus,
    AlertType,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    RiskLevel,
    StrategyStatus,
    TransactionStatus,
    TransactionType,
    UserRole,
)
from .settings import Settings, get_settings

# Core configuration exports only
__all__ = [
    "AlertStatus",
    "AlertType",
    # Constants
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PositionSide",
    "RiskLevel",
    # Settings
    "Settings",
    "StrategyStatus",
    "TransactionStatus",
    "TransactionType",
    "UserRole",
    "get_settings",
]
