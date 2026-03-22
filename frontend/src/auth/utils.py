"""
Utility functions for authentication operations.
Based on notebook: 01_auth_endpoints_testing.ipynb
"""

import uuid
import time
from typing import Dict, Any


def generate_test_user_data() -> Dict[str, Any]:
    """
    Generate test user data with unique identifiers.

    Returns:
        Dictionary with user registration data
    """
    unique_id = str(uuid.uuid4())[:8]
    timestamp = int(time.time())

    return {
        "email": f"testuser_{unique_id}_{timestamp}@example.com",
        "username": f"testuser_{unique_id}",
        "first_name": "Test",
        "last_name": "User",
        "password": "TestPassword123!",
    }


def validate_email(email: str) -> bool:
    """
    Validate email format.

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    import re

    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(email_regex, email) is not None


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength.

    Args:
        password: Password to validate

    Returns:
        Tuple of (is_valid: bool, message: str)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"

    return True, "Password is strong"


def format_user_display(user_data: Dict[str, Any]) -> str:
    """
    Format user data for display.

    Args:
        user_data: User data dictionary

    Returns:
        Formatted string for display
    """
    if not user_data:
        return "No user data"

    parts = []

    if "username" in user_data:
        parts.append(f"**Username:** {user_data['username']}")

    if "email" in user_data:
        parts.append(f"**Email:** {user_data['email']}")

    if "first_name" in user_data or "last_name" in user_data:
        name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
        if name:
            parts.append(f"**Name:** {name}")

    if "id" in user_data:
        parts.append(f"**ID:** {user_data['id']}")

    return "\n".join(parts)


def mask_token(token: str, visible_chars: int = 10) -> str:
    """
    Mask a token for display purposes.

    Args:
        token: Token to mask
        visible_chars: Number of characters to show at start

    Returns:
        Masked token string
    """
    if not token or len(token) <= visible_chars:
        return token

    return f"{token[:visible_chars]}...{'*' * 10}"
