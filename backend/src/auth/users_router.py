"""
Users router for the Crypto Trading Bot API.
Provides endpoints for user management, profiles, and settings.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth.dependencies import get_current_admin_user, get_current_user
from auth.models import User as UserModel
from auth.schemas import (
    BinanceCredentialsStatus,
    BinanceCredentialsUpdate,
    ExchangeCredentialResponse,
    UserResponse,
    UserSettingsUpdate,
    UserUpdate,
)
from auth.user_service import user_service

# Define a constant for the error message
USER_NOT_FOUND_MSG = "User not found"
TESTNET_EXCHANGE_CREDENTIAL_ID = "binance_spot_testnet"
LEGACY_EXCHANGE_CREDENTIAL_ID = "binance"

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: UserModel = Depends(get_current_user),
) -> UserResponse:
    """
    Get current user's profile information.

    Returns the authenticated user's profile data.
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate, current_user: UserModel = Depends(get_current_user)
) -> UserResponse:
    """
    Update current user's profile information.

    - **email**: New email address (must be unique)
    - **username**: New username (must be unique)
    - **first_name**: New first name
    - **last_name**: New last name
    """
    try:
        updated_user = user_service.update_user(current_user.id, user_update)
        return updated_user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user profile: {e!s}",
        ) from None


@router.delete("/me")
async def delete_current_user_account(
    current_user: UserModel = Depends(get_current_user),
) -> dict:
    """
    Delete current user's account.

    This action is irreversible and will remove all user data.
    """
    try:
        success = user_service.delete_user(current_user.id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete user account",
            )

        return {"message": "Account successfully deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete account: {e!s}",
        ) from None


@router.get("/me/settings")
async def get_user_settings(
    current_user: UserModel = Depends(get_current_user),
) -> dict:
    """
    Get current user's settings and preferences.
    """
    try:
        settings = user_service.get_user_settings(current_user.id)
        return settings or {}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user settings: {e!s}",
        ) from None


@router.get("/me/export")
async def export_current_user_data(
    current_user: UserModel = Depends(get_current_user),
) -> dict:
    """
    Export current user's personal data for portability.
    """
    try:
        return user_service.export_user_data(current_user.id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export user data: {e!s}",
        ) from e


@router.put("/me/settings")
async def update_user_settings(
    settings_update: UserSettingsUpdate,
    current_user: UserModel = Depends(get_current_user),
) -> dict:
    """
    Update current user's settings and preferences.

    - **theme**: UI theme preference
    - **risk_profile**: Risk tolerance level
    - **notification_preferences**: Notification settings
    """
    try:
        updated_settings = user_service.update_user_settings(current_user.id, settings_update)
        return updated_settings

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user settings: {e!s}",
        ) from None


@router.get("/me/binance-credentials/status", response_model=BinanceCredentialsStatus)
async def get_binance_credentials_status(
    current_user: UserModel = Depends(get_current_user),
) -> BinanceCredentialsStatus:
    """
    Return whether the authenticated user has Binance credentials configured.

    The response never exposes the API secret. The API key is returned only as a
    masked display value.
    """
    try:
        return user_service.get_binance_credentials_status(current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Binance credentials status: {e!s}",
        ) from None


@router.put("/me/binance-credentials", response_model=BinanceCredentialsStatus)
async def save_binance_credentials(
    credentials: BinanceCredentialsUpdate,
    current_user: UserModel = Depends(get_current_user),
) -> BinanceCredentialsStatus:
    """
    Save Binance credentials for the authenticated user.

    Credentials are encrypted server-side before being stored and are never
    returned by the API.
    """
    try:
        return user_service.save_binance_credentials(
            current_user.id,
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            password_confirmation=credentials.password_confirmation,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save Binance credentials: {e!s}",
        ) from None


@router.delete("/me/binance-credentials", response_model=BinanceCredentialsStatus)
async def delete_binance_credentials(
    current_user: UserModel = Depends(get_current_user),
) -> BinanceCredentialsStatus:
    """
    Delete Binance credentials for the authenticated user.
    """
    try:
        return user_service.delete_binance_credentials(current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete Binance credentials: {e!s}",
        ) from None


def _exchange_credential_response(status_payload: BinanceCredentialsStatus) -> ExchangeCredentialResponse:
    return ExchangeCredentialResponse(
        id=TESTNET_EXCHANGE_CREDENTIAL_ID,
        exchange="binance",
        environment="testnet",
        configured=status_payload.configured,
        updated_at=status_payload.updated_at,
        api_key_masked=status_payload.api_key_masked,
        permissions_checked=status_payload.permissions_checked,
        last_verified_at=status_payload.last_verified_at,
    )


@router.get("/me/exchange-credentials", response_model=list[ExchangeCredentialResponse])
async def list_exchange_credentials(
    current_user: UserModel = Depends(get_current_user),
) -> list[ExchangeCredentialResponse]:
    """List configured exchange credentials. Only Binance Spot Testnet is supported."""
    credentials = user_service.list_exchange_credentials(current_user.id)
    if credentials:
        return credentials
    credential_status = user_service.get_binance_credentials_status(current_user.id)
    return [_exchange_credential_response(credential_status)] if credential_status.configured else []


@router.post("/me/exchange-credentials", response_model=ExchangeCredentialResponse)
async def save_exchange_credentials(
    credentials: BinanceCredentialsUpdate,
    current_user: UserModel = Depends(get_current_user),
) -> ExchangeCredentialResponse:
    """Save Binance Spot Testnet credentials using the architecture target route name."""
    credential_status = user_service.save_binance_credentials(
        current_user.id,
        api_key=credentials.api_key,
        api_secret=credentials.api_secret,
        password_confirmation=credentials.password_confirmation,
    )
    credentials = user_service.list_exchange_credentials(current_user.id)
    return credentials[0] if credentials else _exchange_credential_response(credential_status)


@router.delete("/me/exchange-credentials/{credential_id}", response_model=ExchangeCredentialResponse)
async def delete_exchange_credential(
    credential_id: str,
    current_user: UserModel = Depends(get_current_user),
) -> ExchangeCredentialResponse:
    """Delete Binance Spot Testnet credentials by credential id."""
    if credential_id not in {TESTNET_EXCHANGE_CREDENTIAL_ID, LEGACY_EXCHANGE_CREDENTIAL_ID}:
        credential = user_service.get_exchange_credential(current_user.id, credential_id)
        if credential is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exchange credential not found")
    credential_status = user_service.delete_binance_credentials(current_user.id)
    return _exchange_credential_response(credential_status)


@router.post("/me/exchange-credentials/{credential_id}/verify", response_model=ExchangeCredentialResponse)
async def verify_exchange_credential(
    credential_id: str,
    current_user: UserModel = Depends(get_current_user),
) -> ExchangeCredentialResponse:
    """Verify Binance Spot Testnet credentials and store the permission-check status."""
    if credential_id not in {TESTNET_EXCHANGE_CREDENTIAL_ID, LEGACY_EXCHANGE_CREDENTIAL_ID}:
        credential = user_service.get_exchange_credential(current_user.id, credential_id)
        if credential is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exchange credential not found")
    return user_service.verify_exchange_credential(current_user.id, credential_id)


# Admin-only endpoints
@router.get("/", response_model=list[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of users to return"),
    search: str | None = Query(None, description="Search users by username or email"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    is_admin: bool | None = Query(None, description="Filter by admin status"),
    current_admin: UserModel = Depends(get_current_admin_user),
) -> list[UserResponse]:
    """
    List all users (admin only).

    Supports pagination, search, and filtering options.
    """
    try:
        users = user_service.get_users(
            skip=skip,
            limit=limit,
            search=search,
            is_active=is_active,
            is_admin=is_admin,
        )
        return users

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {e!s}",
        ) from None


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: str, current_admin: UserModel = Depends(get_current_admin_user)) -> UserResponse:
    """
    Get user by ID (admin only).

    - **user_id**: UUID of the user to retrieve
    """
    try:
        user = user_service.get_user_by_id(user_id)

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND_MSG)

        return user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user: {e!s}",
        ) from None


@router.put("/{user_id}", response_model=UserResponse)
async def update_user_by_id(
    user_id: str,
    user_update: UserUpdate,
    current_admin: UserModel = Depends(get_current_admin_user),
) -> UserResponse:
    """
    Update user by ID (admin only).

    - **user_id**: UUID of the user to update
    - **email**: New email address (must be unique)
    - **username**: New username (must be unique)
    - **first_name**: New first name
    - **last_name**: New last name
    - **is_active**: Enable/disable user account
    """
    try:
        user = user_service.get_user_by_id(user_id)

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND_MSG)

        updated_user = user_service.update_user(user_id, user_update)
        return updated_user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {e!s}",
        ) from None


@router.delete("/{user_id}")
async def delete_user_by_id(user_id: str, current_admin: UserModel = Depends(get_current_admin_user)) -> dict:
    """
    Delete user by ID (admin only).

    - **user_id**: UUID of the user to delete
    """
    try:
        user = user_service.get_user_by_id(user_id)

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND_MSG)

        # Prevent self-deletion
        if user_id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account",
            )

        success = user_service.delete_user(user_id)

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to delete user")

        return {"message": f"User {user_id} successfully deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {e!s}",
        ) from None


@router.post("/{user_id}/activate")
async def activate_user(user_id: str, current_admin: UserModel = Depends(get_current_admin_user)) -> dict:
    """
    Activate user account (admin only).

    - **user_id**: UUID of the user to activate
    """
    try:
        user = user_service.get_user_by_id(user_id)

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND_MSG)

        if user.is_active:
            return {"message": "User is already active"}

        user_service.activate_user(user_id)

        return {"message": f"User {user_id} successfully activated"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate user: {e!s}",
        ) from None


@router.post("/{user_id}/deactivate")
async def deactivate_user(user_id: str, current_admin: UserModel = Depends(get_current_admin_user)) -> dict:
    """
    Deactivate user account (admin only).

    - **user_id**: UUID of the user to deactivate
    """
    try:
        user = user_service.get_user_by_id(user_id)

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND_MSG)

        # Prevent self-deactivation
        if user_id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account",
            )

        if not user.is_active:
            return {"message": "User is already inactive"}

        user_service.deactivate_user(user_id)

        return {"message": f"User {user_id} successfully deactivated"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate user: {e!s}",
        ) from None


@router.post("/{user_id}/make-admin")
async def make_user_admin(user_id: str, current_admin: UserModel = Depends(get_current_admin_user)) -> dict:
    """Grant admin privileges to a user (admin only)."""
    try:
        user = user_service.get_user_by_id(user_id)

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND_MSG)

        if user.is_admin:
            return {"message": "User is already admin"}

        user_service.make_admin(user_id)
        return {"message": f"User {user_id} successfully promoted to admin"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to promote user: {e!s}",
        ) from None


@router.post("/{user_id}/remove-admin")
async def remove_user_admin(user_id: str, current_admin: UserModel = Depends(get_current_admin_user)) -> dict:
    """Remove admin privileges from a user (admin only)."""
    try:
        user = user_service.get_user_by_id(user_id)

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=USER_NOT_FOUND_MSG)

        if user_id == current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove your own admin role",
            )

        if not user.is_admin:
            return {"message": "User is already non-admin"}

        user_service.remove_admin(user_id)
        return {"message": f"Admin privileges removed from user {user_id}"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove admin role: {e!s}",
        ) from None
