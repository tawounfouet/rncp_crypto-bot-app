"""
Authentication module for Streamlit client.
Based on notebook: 01_auth_endpoints_testing.ipynb

Usage:
    from auth import AuthManager

    auth_manager = AuthManager()
    success, message = auth_manager.login("username", "password")
"""

from .api_client import AuthAPIClient, APIResponse
from .auth_manager import AuthManager
from .utils import (
    validate_email,
    validate_password_strength,
    format_user_display,
    mask_token,
    generate_test_user_data,
)

__all__ = [
    "AuthAPIClient",
    "APIResponse",
    "AuthManager",
    "validate_email",
    "validate_password_strength",
    "format_user_display",
    "mask_token",
    "generate_test_user_data",
]
