"""
Common Pydantic schemas for the Crypto Trading Bot application.
Contains base schemas, pagination, and shared response models.
"""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseResponse(BaseModel):
    """Base response model with common fields."""

    success: bool = True
    message: str | None = None
    data: Any | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ErrorResponse(BaseResponse):
    """Error response model."""

    success: bool = False
    error_code: str | None = None
    details: dict | None = None


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Page size")
    sort_by: str | None = Field(None, description="Sort field")
    sort_order: str = Field("asc", pattern="^(asc|desc)$", description="Sort order")


class PaginationInfo(BaseModel):
    """Pagination information."""

    page: int
    size: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseResponse, Generic[T]):
    """Paginated response model."""

    data: list[T]
    pagination: PaginationInfo


class StatusResponse(BaseModel):
    """Status response for health checks."""

    status: str
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    services: dict | None = None


# Update forward references
PaginatedResponse.model_rebuild()
