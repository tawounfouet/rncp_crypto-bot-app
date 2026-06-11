"""
User-related Pydantic schemas for the Crypto Trading Bot application.
Contains schemas for user creation, authentication, and responses.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from shared.schemas.common import BaseResponse


class ThemeEnum(StrEnum):
    """Available UI themes."""

    LIGHT = "light"
    DARK = "dark"


class RiskProfileEnum(StrEnum):
    """Available risk profiles."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


# User Creation and Updates
class UserCreate(BaseModel):
    """Schema for user creation."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "username": "trader123",
                "first_name": "John",
                "last_name": "Doe",
                "password": "SecurePassword123!",
            }
        }
    )


class UserUpdate(BaseModel):
    """Schema for user updates."""

    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None

    model_config = ConfigDict(json_schema_extra={"example": {"first_name": "John", "last_name": "Doe Updated"}})


class PasswordChange(BaseModel):
    """Schema for password change."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str


# User Settings
class UserSettingsUpdate(BaseModel):
    """Schema for user settings updates."""

    theme: ThemeEnum | None = None
    risk_profile: RiskProfileEnum | None = None
    notification_preferences: dict | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "theme": "dark",
                "risk_profile": "moderate",
                "notification_preferences": {
                    "email": True,
                    "push": False,
                    "trading_alerts": True,
                },
            }
        }
    )


# User Responses
class UserBase(BaseModel):
    """Base user fields for responses."""

    id: str
    email: EmailStr
    username: str
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool
    is_admin: bool
    last_active_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserResponse(UserBase):
    """Complete user response."""

    model_config = ConfigDict(from_attributes=True)


class UserPublic(BaseModel):
    """Public user information (limited fields)."""

    id: str
    username: str
    first_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserSettings(BaseModel):
    """User settings response."""

    theme: ThemeEnum
    risk_profile: RiskProfileEnum
    notification_preferences: dict
    has_binance_credentials: bool = False

    model_config = ConfigDict(from_attributes=True)


class UserProfile(UserResponse):
    """Extended user profile with settings."""

    settings: UserSettings | None = None

    model_config = ConfigDict(from_attributes=True)


# Authentication
class LoginRequest(BaseModel):
    """Login request schema."""

    username: str  # Can be username or email
    password: str

    model_config = ConfigDict(
        json_schema_extra={"example": {"username": "trader123", "password": "SecurePassword123!"}}
    )


class TokenResponse(BaseResponse):
    """Token response after successful login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int  # seconds
    user: UserResponse


class TokenRefresh(BaseModel):
    """Token refresh request."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout request (optional token for specific session)."""

    refresh_token: str | None = None


class BinanceCredentialsUpdate(BaseModel):
    """Payload for saving Binance API credentials."""

    api_key: str = Field(..., min_length=1, max_length=1024)
    api_secret: str = Field(..., min_length=1, max_length=1024)
    password_confirmation: str = Field(..., min_length=1, max_length=100)


class BinanceCredentialsStatus(BaseModel):
    """Safe status response for Binance API credentials."""

    configured: bool
    updated_at: datetime | None = None
    api_key_masked: str = ""


# User Lists and Statistics
class UserStats(BaseModel):
    """User statistics."""

    total_strategies: int
    active_deployments: int
    total_orders: int
    total_trades: int
    profit_loss: float
    win_rate: float

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseResponse):
    """Response for user list (admin only)."""

    users: list[UserPublic]


class UserCreateResponse(BaseResponse):
    """Response after user creation."""

    user: UserResponse


class UserUpdateResponse(BaseResponse):
    """Response after user update."""

    user: UserResponse
