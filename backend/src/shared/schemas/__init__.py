"""
Shared schemas package.
"""

from .common import BaseResponse, ErrorResponse, PaginatedResponse, PaginationInfo

__all__ = [
    "BaseResponse",
    "ErrorResponse",
    "PaginatedResponse",
    "PaginationInfo",
]
