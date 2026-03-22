"""
Common Pydantic schemas for the Crypto Trading Bot application.
Contains base schemas, pagination, and shared response models.
"""

from typing import Generic, List, Optional, TypeVar, Any
from pydantic import BaseModel, Field
from datetime import datetime

T = TypeVar("T")


class BaseResponse(BaseModel):
    """Base response model with common fields."""

    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseResponse):
    """Error response model."""

    success: bool = False
    error_code: Optional[str] = None
    details: Optional[dict] = None


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Page size")
    sort_by: Optional[str] = Field(None, description="Sort field")
    sort_order: str = Field("asc", pattern="^(asc|desc)$", description="Sort order")


class PaginatedResponse(BaseResponse, Generic[T]):
    """Paginated response model."""

    data: List[T]
    pagination: "PaginationInfo"


class PaginationInfo(BaseModel):
    """Pagination information."""

    page: int
    size: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool


class StatusResponse(BaseModel):
    """Status response for health checks."""

    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Optional[dict] = None


# Update forward references
PaginatedResponse.model_rebuild()
