"""
Custom exceptions for the Crypto Trading Bot application.
"""

from typing import Any


class CryptoBotException(Exception):
    """Base exception for Crypto Trading Bot."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(CryptoBotException):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.field = field
        super().__init__(message, details)


class NotFoundError(CryptoBotException):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        message: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ):
        self.resource_type = resource_type
        self.resource_id = resource_id
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
        super().__init__(message, details)


class BusinessLogicError(CryptoBotException):
    """Raised when business logic constraints are violated."""


class AuthenticationError(CryptoBotException):
    """Raised when authentication fails."""


class AuthorizationError(CryptoBotException):
    """Raised when authorization fails."""


class ExternalServiceError(CryptoBotException):
    """Raised when external service calls fail."""

    def __init__(
        self,
        message: str,
        service_name: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.service_name = service_name
        if service_name:
            details = details or {}
            details["service_name"] = service_name
        super().__init__(message, details)


class RateLimitError(ExternalServiceError):
    """Raised when rate limits are exceeded."""


class InsufficientFundsError(BusinessLogicError):
    """Raised when insufficient funds for trading operations."""


class StrategyExecutionError(CryptoBotException):
    """Raised when strategy execution fails."""


class DataError(CryptoBotException):
    """Raised when data processing or retrieval fails."""
