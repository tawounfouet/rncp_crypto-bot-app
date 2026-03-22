"""
Core module for Crypto Trading Bot.
"""

from .exceptions import (
    CryptoBotException,
    ValidationError,
    NotFoundError,
    BusinessLogicError,
    AuthenticationError,
    AuthorizationError,
    ExternalServiceError,
    RateLimitError,
    InsufficientFundsError,
    StrategyExecutionError,
    DataError,
)

__all__ = [
    "CryptoBotException",
    "ValidationError",
    "NotFoundError",
    "BusinessLogicError",
    "AuthenticationError",
    "AuthorizationError",
    "ExternalServiceError",
    "RateLimitError",
    "InsufficientFundsError",
    "StrategyExecutionError",
    "DataError",
]
