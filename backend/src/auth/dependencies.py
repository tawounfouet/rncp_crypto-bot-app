"""
Authentication dependencies for route protection.
Provides dependency injection for user authentication and authorization.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from shared.config.security import decrypt_secret, encrypt_secret

from auth.models import User
from auth.service import auth_service

# Security scheme for JWT Bearer tokens
security = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> User:
    """
    Dependency to get the current authenticated user.

    Validates the JWT token and returns the associated user.
    Raises HTTP 401 if token is invalid or user not found.
    """
    try:
        # Extract token from Authorization header
        token = credentials.credentials

        # Get user from token using the auth service
        user = auth_service.get_current_user(token)

        return user

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Dependency to get the current active user.

    Ensures the user account is active.
    Raises HTTP 400 if user account is inactive.
    """
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account")

    return current_user


def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Dependency to get the current admin user.

    Ensures the user has admin privileges.
    Raises HTTP 403 if user is not an admin.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required.",
        )

    return current_user


# Optional dependencies for routes that work with or without authentication
def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User | None:
    """
    Optional dependency to get the current user.

    Returns None if no valid token is provided instead of raising an error.
    Useful for routes that work both with and without authentication.
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        user = auth_service.get_current_user(token)
        return user if user.is_active else None
    except Exception:
        return None


def encrypt_value(plaintext: str) -> dict:
    return encrypt_secret(plaintext)


def decrypt_value(ciphertext_b64: str, nonce_b64: str) -> str:
    return decrypt_secret(ciphertext_b64, nonce_b64)
