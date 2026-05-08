"""
Core module for Crypto Trading Bot.
"""

from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessLogicError,
    CryptoBotException,
    DataError,
    ExternalServiceError,
    InsufficientFundsError,
    NotFoundError,
    RateLimitError,
    StrategyExecutionError,
    ValidationError,
)

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "BusinessLogicError",
    "CryptoBotException",
    "DataError",
    "ExternalServiceError",
    "InsufficientFundsError",
    "NotFoundError",
    "RateLimitError",
    "StrategyExecutionError",
    "ValidationError",
]
