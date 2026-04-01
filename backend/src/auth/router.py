"""
Authentication router for the Crypto Trading Bot API.
Provides endpoints for user authentication, registration, and token management.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from auth.schemas import LoginRequest, TokenResponse, UserCreate
from auth.service import auth_service
from auth.user_service import user_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: Request, user_data: UserCreate) -> TokenResponse:
    """
    Register a new user and return authentication tokens.

    - **email**: User's email address (must be unique)
    - **username**: User's username (must be unique)
    - **password**: User's password (will be hashed)
    - **full_name**: User's full name (optional)
    - **is_admin**: Whether user should have admin privileges (default: False)
    """
    try:
        # Create user through user service
        user = user_service.create_user(user_data)

        # Get client info for session tracking
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Create tokens for the new user
        tokens = auth_service.create_user_tokens(user, ip_address, user_agent)

        return tokens

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register user: {e!s}",
        ) from None


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenResponse:
    """
    Authenticate user and return access tokens.

    Compatible with OAuth2 password flow.
    - **username**: Username or email address
    - **password**: User's password
    """
    try:
        # Authenticate user
        user = auth_service.authenticate_user(form_data.username, form_data.password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get client info for session tracking
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Create tokens
        tokens = auth_service.create_user_tokens(user, ip_address, user_agent)

        return tokens

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {e!s}",
        ) from None


@router.post("/login/json", response_model=TokenResponse)
async def login_json(request: Request, login_data: LoginRequest) -> TokenResponse:
    """
    Authenticate user with JSON payload and return access tokens.

    Alternative to OAuth2 form-based login.
    - **username**: Username or email address
    - **password**: User's password
    """
    try:
        # Authenticate user
        user = auth_service.authenticate_user(login_data.username, login_data.password)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get client info for session tracking
        ip_address = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Create tokens
        tokens = auth_service.create_user_tokens(user, ip_address, user_agent)

        return tokens

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {e!s}",
        ) from None


@router.post("/refresh")
async def refresh_token(refresh_token: str) -> dict:
    """
    Refresh access token using refresh token.

    - **refresh_token**: Valid refresh token
    """
    try:
        new_access_token = auth_service.refresh_access_token(refresh_token)

        return {"access_token": new_access_token, "token_type": "bearer"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {e!s}",
        ) from None


@router.post("/logout")
async def logout(refresh_token: str) -> dict:
    """
    Logout user by invalidating refresh token.

    - **refresh_token**: Refresh token to invalidate
    """
    try:
        success = auth_service.logout_user(refresh_token)

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refresh token")

        return {"message": "Successfully logged out"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {e!s}",
        ) from None


@router.post("/logout-all")
async def logout_all_sessions(user_id: str) -> dict:
    """
    Logout user from all sessions.

    - **user_id**: User ID to logout from all sessions
    """
    try:
        count = auth_service.logout_all_sessions(user_id)

        return {
            "message": f"Successfully logged out from {count} sessions",
            "sessions_terminated": count,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout all failed: {e!s}",
        ) from None
