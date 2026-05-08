"""
Authentication module for Streamlit client.
Based on notebook: 01_auth_endpoints_testing.ipynb

Usage:
    from auth import AuthManager

    auth_manager = AuthManager()
    success, message = auth_manager.login("username", "password")
"""

from .api_client import APIResponse, AuthAPIClient
from .auth_manager import AuthManager
from .utils import (
    format_user_display,
    generate_test_user_data,
    mask_token,
    validate_email,
    validate_password_strength,
)

__all__ = [
    "APIResponse",
    "AuthAPIClient",
    "AuthManager",
    "format_user_display",
    "generate_test_user_data",
    "mask_token",
    "validate_email",
    "validate_password_strength",
]
