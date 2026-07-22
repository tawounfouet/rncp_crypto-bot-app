"""Schemas relatifs a l'authentification et a la session UI."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator
from schemas.common import UserRole, UserStatus


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str | None = None
    email: str
    username: str | None = None
    password: str
    confirm_password: str

    @field_validator("first_name")
    @classmethod
    def ensure_first_name(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Le prenom est requis.")
        return text

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None


class MockUser(BaseModel):
    id: str
    first_name: str
    last_name: str | None = None
    email: str
    password: str
    role: UserRole = Field(default=UserRole.USER)
    status: UserStatus = Field(default=UserStatus.ENABLED)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_login: datetime | None = None
    exchange: str = "binance"
    exchange_configured: bool = False
    failed_login_count: int = 0

    @property
    def display_name(self) -> str:
        parts = [self.first_name.strip()]
        if self.last_name and self.last_name.strip():
            parts.append(self.last_name.strip())
        return " ".join(parts)


class AuthResult(BaseModel):
    success: bool
    message: str
    user: MockUser | None = None
