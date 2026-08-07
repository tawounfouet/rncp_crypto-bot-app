"""
Users router for the Crypto Trading Bot API.
Provides endpoints for user management, profiles, and settings.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from shared.schemas.common import BaseResponse

from auth.dependencies import get_current_admin_user, get_current_user
from auth.models import User as UserModel
from auth.schemas import ApiCredentialCreate, ApiCredentialResponse, UserResponse, UserSettingsUpdate, UserUpdate
from auth.user_service import user_service

# Define a constant for the error message
USER_NOT_FOUND_MSG = "User not found"

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: UserModel = Depends(get_current_user),
) -> UserResponse:
    """Get current user's profile information."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate, current_user: UserModel = Depends(get_current_user)
) -> UserResponse:
    """Update current user's profile information."""
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
    """Delete current user's account."""
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
    """Get current user's settings and preferences."""
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
    """Export current user's personal data for portability."""
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
    """Update current user's settings and preferences."""
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


@router.get("/me/api-keys", response_model=list[ApiCredentialResponse])
async def list_api_credentials(
    current_user: UserModel = Depends(get_current_user),
) -> list[ApiCredentialResponse]:
    """List all stored API credentials for the current user (masked)."""
    try:
        creds = user_service.list_api_credentials(current_user.id)
        return [ApiCredentialResponse(**c) for c in creds]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API credentials: {e!s}",
        ) from None


@router.post("/me/api-keys", response_model=ApiCredentialResponse, status_code=status.HTTP_201_CREATED)
async def add_api_credential(
    credential: ApiCredentialCreate,
    current_user: UserModel = Depends(get_current_user),
) -> ApiCredentialResponse:
    """Add a new named API credential."""
    try:
        result = user_service.add_api_credential(
            current_user.id,
            label=credential.label,
            exchange=credential.exchange,
            api_key=credential.api_key,
            api_secret=credential.api_secret,
        )
        return ApiCredentialResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add API credential: {e!s}",
        ) from None


@router.put("/me/api-keys/{key_id}/primary", status_code=status.HTTP_200_OK)
async def set_primary_api_credential(
    key_id: str,
    current_user: UserModel = Depends(get_current_user),
) -> dict:
    """Mark an API credential as primary for its exchange."""
    try:
        updated = user_service.set_primary_credential(current_user.id, key_id)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
        return {"success": True, "message": "Clef définie comme principale."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set primary credential: {e!s}",
        ) from None


@router.delete("/me/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_credential(
    key_id: str,
    current_user: UserModel = Depends(get_current_user),
) -> None:
    """Delete an API credential by ID."""
    try:
        removed = user_service.remove_api_credential(current_user.id, key_id)
        if not removed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete API credential: {e!s}",
        ) from None


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
    """List all users (admin only)."""
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
    """Get user by ID (admin only)."""
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
    """Update user by ID (admin only)."""
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
    """Delete user by ID (admin only)."""
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
    """Activate user account (admin only)."""
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
    """Deactivate user account (admin only)."""
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


@router.post("/purge-inactive", response_model=BaseResponse)
def purge_inactive_users(
    days: int = Query(730, ge=1, description="Seuil d'inactivite en jours"),
) -> BaseResponse:
    """Purge les comptes inactifs depuis plus de ``days`` jours.

    Appele par Airflow (DAG ``cryptobot_purge_inactive_users``), pas par un
    utilisateur final -- pas d'authentification, meme principe que
    ``POST /strategies/deployments/execute-active``.
    """
    try:
        deleted = user_service.delete_inactive_users_older_than(days=days)
        return BaseResponse(
            success=True,
            message=f"Deleted {deleted} inactive users",
            data={"deleted": deleted},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to purge inactive users: {e!s}",
        ) from None
